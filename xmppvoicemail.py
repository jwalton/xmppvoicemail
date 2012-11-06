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

from phonenumberutils import stripNumber, toPrettyNumber, toNormalizedNumber, validateNumber
from models import XmppUser

class Owner:
    """ Represents the owner of an XmppVoiceMail
    """
    
    def __init__(self, phoneNumber, jid, emailAddress):
        self.phoneNumber = phoneNumber
        self.jid = jid
        self.emailAddress = emailAddress
    
    
class XmppVoiceMail:
    def __init__(self, owner):
        self._APP_ID = app_identity.get_application_id()
        self._DEV_ENVIRONMENT = os.environ['SERVER_SOFTWARE'].startswith('Development')
        self._owner = owner

    def handleIncomingCall(self, fromNumber, callStatus):
        nickname = self._getNicknameForNumber(fromNumber)
        displayNumber = nickname
        if nickname == config.DEFAULT_SENDER:
            displayNumber = toPrettyNumber(fromNumber)

        self._sendMessageToOwner("Call from: " + displayNumber + " status:" + callStatus, nickname, fromNumber)

    def handleVoiceMail(self, fromNumber, transcriptionText, recordingUrl):        
        nickname = self._getNicknameForNumber(fromNumber)
        displayNumber = nickname
        if nickname == config.DEFAULT_SENDER:
            displayNumber = toPrettyNumber(fromNumber)

        body = "New message from " + displayNumber + ": " + transcriptionText + " Recording:" + recordingUrl
        return self._sendMessageToOwner(body, nickname, fromNumber)

    def handleIncomingSms(self, fromNumber, toNumber, body):
        """Handle and incoming SMS message from the network.
        """
        
        # Find the XMPP user to send this from
        nickname = self._getNicknameForNumber(fromNumber)
        if nickname == config.DEFAULT_SENDER:
            body = "" + toPrettyNumber(fromNumber) + ": " + body

        # Forward the message to the owner
        self._sendMessageToOwner(body, nickname, fromNumber)

    def handleIncomingXmpp(self, message):
        """Handle and incoming XMPP message from the owner.
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
                self._sendSMS(toNumber, body)


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
                self._sendSMS(toNumber, body)


    def _sendSMS(self, toNumber, body):
        # TODO: Reimplement
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

    def _getNicknameForNumber(self, number):
        """ Find the nickname associated with a number.
        
        Returns the nickname, or none if no nickname can be found.
        """ 
        nickname = None

        # Find the nickname
        normalizedNumber = toNormalizedNumber(number)

        if normalizedNumber in config.NICKNAMES:
            nickname = config.NICKNAMES[normalizedNumber]
        elif len(normalizedNumber) > 0 and \
             normalizedNumber[0] == "1" and \
             normalizedNumber[1:] in config.NICKNAMES:
            nickname = config.NICKNAMES[normalizedNumber[1:]]

        # If we couldn't find a nickname, then send as the default nick, and
        # add the number to the message.
        if nickname is None:
            nickname = config.DEFAULT_SENDER

        return nickname

    _messageRegex = re.compile(r"^([^:]*):(.*)$")

    def _getNumberAndBody(self, toAddress, body):
        """Get the destination phone number and the message body from a message.
        
        The message will be either to the DEFAULT_SENDER, in which case
        the body will be of the format "number:message", or else the message
        will be to a nickname, and the body will just be the message.

        This returns the tuple (toNumber, body, errorMessage), where toNumber
        is the SMS number to send this message to, and body is the message
        content.  If errorMessage is not None, then the other two fields are
        undefined.
        """
        toNickname = toAddress.split("@")[0]
        toNumber = None
        errorMessage = None

        if toNickname == config.DEFAULT_SENDER:
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
            # Reverse lookup in config.NICKNAMES
            for number in config.NICKNAMES.keys():
                if config.NICKNAMES[number].lower() == toNickname.lower():
                    toNumber = "+" + toNormalizedNumber(number)
                    break

            if not toNumber:
                if validateNumber(toNickname):
                    # This is a phone number
                    toNumber = toNormalizedNumber(toNickname)
                else:
                    errorMessage = "Unknown nickname: " + toNickname

        return (toNumber, body, errorMessage)


    def _getNumberAndBodyFromEmailMessage(self, emailMessage, messageBody):
        return self._getNumberAndBody(emailMessage.to, messageBody)


    def _getNumberAndBodyFromXmppMessage(self, xmppMessage):
        return self._getNumberAndBody(xmppMessage.to.split("/")[0], xmppMessage.body)

    def _sendMessageToOwner(self, message, fromNickname=None, fromNumber=None):
        """
        Send a message to the user who owns this XmppVoiceMail account.

        fromNickname is the nickname to send the message from.

        Returns True on success, False on failure.
        """
        answer = False

        if not fromNickname:
            fromNickname = config.DEFAULT_SENDER

        # TODO: Make sure owner is subscribed to fromNickname.
        
        xmppOnline = False
        if self._owner.jid.endswith("@gmail.com") and not self._DEV_ENVIRONMENT:
            # This always shows the user online in the dev environment, so fall back on the DB for dev.
            xmppOnline = xmpp.get_presence(self._owner.jid)
        else:
            user = XmppUser.getFromJid(self._owner.jid)
            if user:
                xmppOnline = user.presence
                
        if xmppOnline:
            # Send the message as XMPP
            result = self._sendXMPPMessage(
                message=message,
                fromNickname=fromNickname)
            answer = result == xmpp.NO_ERROR
        else:
            # Send an email
            self._sendEmailMessage(
                subject=message,
                fromNickname=fromNickname,
                fromNumber=fromNumber)
            answer = True

        return answer


    def _sendXMPPMessage(self, message, fromNickname=None):
        if not fromNickname:
            fromNickname = config.DEFAULT_SENDER

        logging.debug("Sending XMPP message to " + self._owner.jid + ": " + message)

        fromJid = fromNickname + "@" + self._APP_ID + ".appspotchat.com"
        xmpp.send_invite(self._owner.jid, fromJid)
        return xmpp.send_message(self._owner.jid, message, from_jid=fromJid)


    def _sendEmailMessage(self, subject, body=None, fromNickname=None, fromNumber=None):
        if not body:
            body = ""

        if (not fromNickname) or (fromNickname == config.DEFAULT_SENDER):
            if fromNumber:
                fromNickname = toNormalizedNumber(fromNumber)
            else:
                fromNickname = config.DEFAULT_SENDER

        logging.debug("Sending eMail message to " + self._owner.emailAddress + ": " + subject)

        fromAddress = fromNickname + "@" + self._APP_ID + ".appspotmail.com"
        mail.send_mail(
            sender=fromAddress,
            to=self._owner.emailAddress,
            subject=subject,
            body=body)

    

