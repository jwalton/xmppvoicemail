import os
import re
import base64
import logging
import urllib

from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.api import app_identity
from google.appengine.api import xmpp

import config

from phonenumberutils import  toPrettyNumber, toNormalizedNumber, validateNumber
from models import XmppUser, Contact

class Owner:
    """ Represents the owner of an XmppVoiceMail
    """
    
    def __init__(self, phoneNumber, jid, emailAddress):
        self.phoneNumber = phoneNumber
        self.jid = jid
        self.emailAddress = emailAddress

class Communications:
    def sendMail(self, sender, to, subject, body):
        mail.send_mail(
            sender=sender,
            to=to,
            subject=subject,
            body=body)
    
    def sendXmppMessage(self, fromJid, toJid, message):
        xmpp.send_message(toJid, message, from_jid=fromJid)
        
    def sendXmppInvite(self, fromJid, toJid):
        xmpp.send_invite(toJid, fromJid)
        
    def getXmppPresence(self, jid):
        return xmpp.get_presence(self._owner.jid)

    def sendSMS(self, toNumber, body):
        logging.info("SMS to " + toNumber + ": " + body)

        if not self._DEV_ENVIRONMENT:
            form_fields = {
                "From": self._owner.phoneNumber,
                "To": toNumber,
                "Body": body
            }
            form_data = urllib.urlencode(form_fields)

            twurl = "https://api.twilio.com/2010-04-01/Accounts/" + config.TWILIO_ACID + "/SMS/Messages"
            logging.debug('The twilio url: ' + twurl)

            result = urlfetch.fetch(url=twurl,
                                    payload=form_data,
                                    method=urlfetch.POST,
                                    headers={'Content-Type': 'application/x-www-form-urlencoded',
                                             "Authorization": "Basic %s" % (base64.encodestring(config.TWILIO_ACID + ":" + config.TWILIO_AUTH)[:-1]).replace('\n', '') })
            logging.debug('reply content: ' + result.content)
    
class XmppVoiceMail:
    """
    Represents a virtual cell phone, which can receive SMS messages and voicemail.
    """
    def __init__(self, owner):
        self._APP_ID = app_identity.get_application_id()
        self._DEV_ENVIRONMENT = os.environ['SERVER_SOFTWARE'].startswith('Development')
        self._owner = owner
        self._communications = Communications()

    def handleIncomingCall(self, fromNumber, callStatus):
        """Handle an incoming call.
        """
        displayFrom = toPrettyNumber(fromNumber)
        
        # Find the XMPP user to send this from
        contact = Contact.getByPhoneNumber(fromNumber)
        if contact:
            displayFrom = contact.name
        else:
            contact = Contact.getDefaultSender()
            
        self._sendMessageToOwner("Call from: " + displayFrom + " status:" + callStatus, contact, fromNumber)

    def handleVoiceMail(self, fromNumber, transcriptionText=None, recordingUrl=None):
        """Handle an incoming voice mail.
        """
        displayFrom = toPrettyNumber(fromNumber)
        
        # Find the XMPP user to send this from
        contact = Contact.getByPhoneNumber(fromNumber)
        if contact:
            displayFrom = contact.name
        else:
            contact = Contact.getDefaultSender()

        body = "New message from " + displayFrom
        if transcriptionText:
            body += ": " + transcriptionText
            
        if recordingUrl:
            body += " - Recording: " + recordingUrl
            
        return self._sendMessageToOwner(body, contact, fromNumber)

    def handleIncomingSms(self, fromNumber, toNumber, body):
        """Handle an incoming SMS message from the network.
        """
        # Find the XMPP user to send this from
        contact = Contact.getByPhoneNumber(fromNumber)
        if not contact:
            contact = Contact.getDefaultSender()
            
        # Forward the message to the owner
        self._sendMessageToOwner(body, contact, fromNumber)

    def handleIncomingXmpp(self, message):
        """Handle an incoming XMPP message from the owner.
        """

        # Make sure the message is from the owner, to stop third parties from
        # using this to spam.
        sender = message.sender.split('/')[0]
        if not sender == self._owner.jid:
            logging.error("Received XMPP message from " + sender)

        else:
            toNumber, body, errorMessage = self._getNumberAndBodyFromXmppMessage(message)

            if errorMessage or (not toNumber):
                # Reply via XMPP to let the sender know we can't route this message
                message.reply("ERROR: " + errorMessage)

            else:
                # Send the message to the SMS number
                self._communications.sendSMS(toNumber, body)


    def handleIncomingEmail(self, mail_message):
        if not self._owner.emailAddress in mail_message.sender:
            logging.warn("Got email from unknown user " + mail_message.sender)
        else:
            logging.debug("Received an email from: " + mail_message.sender)

            # Extract the first message body we can find.
            messageBody = ""
            for content_type, body in mail_message.bodies():
                messageBody += body.decode()
                if messageBody:
                    break

            toNumber, body, errorMessage = \
                self._getNumberAndBodyFromEmailMessage(mail_message, messageBody)

            if errorMessage or (not toNumber):
                # Reply via email to let the sender know we can't route this message
                self._sendEmailMessage(
                    subject = "ERROR: " + errorMessage,
                    body = "Original message:\n" + messageBody)
            else:
                self._communications.sendSMS(toNumber, body)

    def sendXmppInvite(self, nickname):
        """Send an XMPP invite to the owner of this phone for the given nickname.
        """
        fromJid = nickname + "@" + self._APP_ID + ".appspotchat.com"
        self._communications.sendXmppInvite(fromJid, self._owner.jid)

    def getDefaultSenderName(self):
        return Contact.getDefaultSender().name

    _messageRegex = re.compile(r"^([^:]*):(.*)$")

    def _getNumberAndBody(self, toAddress, body):
        """Get the destination phone number and the message body from a message.
        
        The message will be either to the default sender, in which case
        the body will be of the format "number:message", or else the message
        will be to a nickname, and the body will just be the message.

        This returns the tuple (toNumber, body, errorMessage), where toNumber
        is the SMS number to send this message to, and body is the message
        content.  If errorMessage is not None, then the other two fields are
        undefined.
        """
        
        # TODO: Errors should be exceptions.
        toName = toAddress.split("@")[0]
        toNumber = None
        errorMessage = None

        if toName == self.getDefaultSenderName():
            if not ":" in body:
                errorMessage = "Use 'number:message' to send an SMS."
            else:
                # Parse the phone number and body out of the message
                match = self._messageRegex.match(body)
                if not match:
                    errorMessage = "Use 'number:message' to send an SMS."
                else:
                    normalizedNumber = toNormalizedNumber(match.group(1))
                    if not validateNumber(normalizedNumber):
                        errorMessage = "Invalid number."
                    else:
                        body = match.group(2).strip()
                        toNumber = "+" + normalizedNumber
                    
        else:
            contact = Contact.getByName(toName)
            
            if not contact:
                errorMessage = "Unknown nickname: " + toName
            else:
                toNumber = "+" + contact.normalizedPhoneNumber

        return (toNumber, body, errorMessage)


    def _getNumberAndBodyFromEmailMessage(self, emailMessage, messageBody):
        return self._getNumberAndBody(emailMessage.to, messageBody)


    def _getNumberAndBodyFromXmppMessage(self, xmppMessage):
        return self._getNumberAndBody(xmppMessage.to.split("/")[0], xmppMessage.body)

    def _ownerXmppPresent(self):
        xmppOnline = False
        if self._owner.jid.endswith("@gmail.com"):
            # This always shows the user online in the dev environment, so fall back on the DB for dev.
            xmppOnline = self._communications.getXmppPresence(self._owner.jid)
        else:
            user = XmppUser.getByJid(self._owner.jid)
            if user:
                xmppOnline = user.presence
                
        return xmppOnline
    
    def _sendMessageToOwner(self, message, contact=None, fromNumber=None):
        """
        Send a message to the user who owns this XmppVoiceMail account.

        fromNickname is the nickname to send the message from.

        Returns True on success, False on failure.
        """
        answer = False

        defaultSender = Contact.getDefaultSender()
        if not contact:
            contact = defaultSender

        xmppOnline = self._ownerXmppPresent()
                
        sendByEmail = (not xmppOnline) or \
                      ((not contact.subscribed) and (not defaultSender.subscribed)) 
                
        if sendByEmail:
            self._sendEmailMessage(
                subject=message,
                fromContact=contact,
                fromNumber=fromNumber)
            answer = True
             
        else:
            if not contact.subscribed:
                # Need a subscribed contact for XMPP; use the default sender.
                contact = defaultSender

            result = self._sendXMPPMessage(
                message=message,
                fromContact=contact,
                fromNumber=fromNumber)
            answer = result == xmpp.NO_ERROR
                
        return answer


    def _sendXMPPMessage(self, message, fromContact=None, fromNumber=None):
        if not fromContact:
            fromContact = Contact.getDefaultSender()

        # Add the fromNumber to the message if this is from the default sender.
        if fromContact.isDefaultSender() and fromNumber:
            message = toPrettyNumber(fromNumber) + ": " + message

        logging.debug("Sending XMPP message to " + self._owner.jid + ": " + message)

        fromJid = fromContact.name + "@" + self._APP_ID + ".appspotchat.com"
        return self._communications.sendXmppMessage(fromJid, self._owner.jid, message)


    def _sendEmailMessage(self, subject, body=None, fromContact=None, fromNumber=None):
        if not body:
            body = ""

        if not fromContact:
            fromContact = Contact.getDefaultSender()

        fromName = fromContact.name
        if fromNumber:
            fromAddress = toNormalizedNumber(fromNumber)
        elif not fromContact.isDefaultSender():
            fromContact.normalizedPhoneNumber
        else:
            fromAddress = fromName
            
        logging.debug("Sending eMail message to " + self._owner.emailAddress + ": " + subject)

        fromAddress = '"' + fromName + '" <' + fromAddress + "@" + self._APP_ID + ".appspotmail.com>"
        self._communications.sendMail(
            sender=fromAddress,
            to=self._owner.emailAddress,
            subject=subject,
            body=body)

    

