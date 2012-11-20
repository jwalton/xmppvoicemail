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

from phonenumberutils import  toPrettyNumber, stripNumber, toNormalizedNumber, validateNumber
from models import XmppUser, Contact

class XmppVoiceMailException(Exception):
    """ Abstract base class for all XmppVoiceMail errors.
    """
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)

class PermissionException(XmppVoiceMailException):
    """ Thrown when an attempt is made to access a service by a user with insufficient permissions.
    """
    def __init__(self, value):
        super(PermissionException, self).__init__(value)
    

class InvalidParametersException(XmppVoiceMailException):
    """ Thrown when parameters passed to a method are invalid.
    """
    def __init__(self, value):
        super(InvalidParametersException, self).__init__(value)

class Owner:
    """ Represents the owner of an XmppVoiceMail
    """
    
    def __init__(self, phoneNumber, jid, emailAddress):
        self.phoneNumber = phoneNumber
        self.jid = jid
        self.emailAddress = emailAddress

class Communications:
    def __init__(self):
        self._DEV_ENVIRONMENT = os.environ['SERVER_SOFTWARE'].startswith('Development')
    
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
        return xmpp.get_presence(jid)

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
            
        self.sendMessageToOwner("Call from: " + displayFrom + " status:" + callStatus, contact, fromNumber)

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
            
        return self.sendMessageToOwner(body, contact, fromNumber)

    def handleIncomingSms(self, fromNumber, toNumber, body):
        """Handle an incoming SMS message from the network.
        """
        # Find the XMPP user to send this from
        contact = Contact.getByPhoneNumber(fromNumber)
        if not contact:
            contact = Contact.getDefaultSender()
            
        # Forward the message to the owner
        self.sendMessageToOwner(body, contact, fromNumber)

    def handleIncomingXmpp(self, sender, to, messageBody):
        """Handle an incoming XMPP message from the owner.
        
        Raises InvalidParametersException if there are problems with the incoming XMPP message.
        Raises PermissionException if the sender is not authorized to use this service.
        """
        # Make sure the message is from the owner, to stop third parties from
        # using this to spam.
        if not sender == self._owner.jid:
            raise PermissionException("Incorrect XMPP user")

        self._forwardToSms(to, messageBody)

    def handleIncomingEmail(self, sender, to, subject, messageBody):
        """Handle an incoming Email message from the owner.
        
        Raises InvalidParametersException if there are any problems with the format of the email.
        Raises PermissionException if the sender is not authorized to use this service.
        """
        if not self._owner.emailAddress in sender:
            raise PermissionException("Incorrect XMPP user")

        self._forwardToSms(to, messageBody)

    def _forwardToSms(self, to, messageBody):
        toNumber, body = self._getNumberAndBody(to, messageBody)
        self._communications.sendSMS(toNumber, body)


    def sendXmppInvite(self, nickname):
        """Send an XMPP invite to the owner of this phone for the given nickname.
        """
        fromJid = nickname + "@" + self._APP_ID + ".appspotchat.com"
        self._communications.sendXmppInvite(fromJid, self._owner.jid)

    _messageRegex = re.compile(r"^([^:]*):(.*)$")

    def _getNumberAndBody(self, toAddress, body):
        """Get the destination phone number and the message body from a message.
        
        The message will be either to the default sender, in which case
        the body will be of the format "number:message", or else the message
        will be to a nickname, and the body will just be the message.

        This returns the tuple (toNumber, body), where toNumber
        is the SMS number to send this message to, and body is the message
        content.
        
        Raises InvalidParametersException if there are any errors in the input.
        """
        
        toName = toAddress.split("@")[0]
        toNumber = None

        contact = Contact.getByName(toName)
        if not contact:
            raise InvalidParametersException("Unknown contact " + toName)
    
        if not contact.isDefaultSender():
            toNumber = contact.normalizedPhoneNumber
            
        else:
            # Parse the phone number and body out of the message
            match = self._messageRegex.match(body)
            if not match:
                raise InvalidParametersException("Use 'number:message' to send an SMS.")

            toNumber = match.group(1)
            if not validateNumber(toNumber):
                raise InvalidParametersException("Invalid number: " + match.group(1))

            toNumber = toNormalizedNumber(toNumber)
            body = match.group(2).strip()
                    
        return (toNumber, body)


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
    
    def sendMessageToOwner(self, message, contact=None, fromNumber=None):
        """
        Send a message to the user who owns this XmppVoiceMail account.

        contact is the contact to send the message from.
        
        fromNumber is the phone number to send the message from if contact is
        the default sender.

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
            self.sendEmailMessageToOwner(
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


    def sendEmailMessageToOwner(self, subject, body=None, fromContact=None, fromNumber=None):
        if not body:
            body = ""

        if not fromContact:
            fromContact = Contact.getDefaultSender()

        fromName = fromContact.name
        if fromNumber:
            fromAddress = stripNumber(toNormalizedNumber(fromNumber))
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

    

