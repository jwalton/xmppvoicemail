#!/usr/bin/env python
#
# Author: Mick Thompson (dthompson@gmail.com)
#
import os, urllib, logging, base64, re
import webapp2
from google.appengine.ext.webapp import template
from google.appengine.api import xmpp
from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler

from phonenumberutils import stripNumber, toPrettyNumber

import config

DEV_ENVIRONMENT = os.environ['SERVER_SOFTWARE'].startswith('Development')


class XmppUser(db.Model):
    jid = db.StringProperty(required=True)
    presence = db.BooleanProperty(required=True)

    @staticmethod
    def getFromJid(jid):
        q = db.GqlQuery("SELECT * FROM XmppUser WHERE jid = :1", jid)
        return q.get()

class XmppVoiceMail:
    def sendMessageToUser(self, message, fromNickname):
        """
        Send a message to the user who owns this XmppVoiceMail account.

        fromNickname is the nickname to send the message from.

        Returns True on success, False on failure.
        """
        answer = False

        fromUser = fromNickname + "@" + config.XMPP_DOMAIN

        user = XmppUser.getFromJid(config.USERJID)
        if user:
            logging.info("Found user")
        else:
            logging.info("No user: " + config.USERJID)
        if user and user.presence:
            # Send the message as XMPP
            result = self.sendXMPPMessage(message, fromUser)
            answer = result == xmpp.NO_ERROR
        else:
            # Send an email
            mail.send_mail(
                sender=fromUser,
                to=config.USER_EMAIL,
                subject=message,
                body="EOM")
            answer = True

        return answer


    def sendXMPPMessage(self, message, fromJid=None):
        if not fromJid:
            fromJid = config.DEFAULT_SENDER + "@" + config.XMPP_DOMAIN
        logging.debug("Sending XMPP message to " + config.USERJID)
        xmpp.send_invite(config.USERJID, fromJid)
        return xmpp.send_message(config.USERJID, message, from_jid=fromJid)


    def sendSMS(self, toNumber, body):
        logging.info("SMS to " + toNumber + ": " + body)

        if not DEV_ENVIRONMENT:
            form_fields = {
                "From": config.TWILIO_NUMBER,
                "To": toNumber,
                "Body": body
            }
            form_data = urllib.urlencode(form_fields)

            twurl = "https://api.twilio.com/2010-04-01/Accounts/"+config.TWILIO_ACID+"/SMS/Messages"
            logging.debug('The twilio url: ' + twurl)

            result = urlfetch.fetch(url=twurl,
                                    payload=form_data,
                                    method=urlfetch.POST,
                                    headers={'Content-Type': 'application/x-www-form-urlencoded',
                                             "Authorization": "Basic %s" % (base64.encodestring(config.TWILIO_ACID + ":" + config.TWILIO_AUTH)[:-1]).replace('\n', '') })
            logging.debug('reply content: ' + result.content)

    def getNicknameForNumber(self, number):
        nickname = None

        # Find the nickname
        strippedNumber = stripNumber(number)

        if strippedNumber in config.NICKNAMES:
            nickname = config.NICKNAMES[strippedNumber]
        elif len(strippedNumber) > 0 and \
             strippedNumber[0] == "1" and \
             strippedNumber[1:] in config.NICKNAMES:
            nickname = config.NICKNAMES[strippedNumber[1:]]

        # If we couldn't find a nickname, then send as the default nick, and
        # add the number to the message.
        if nickname is None:
            nickname = config.DEFAULT_SENDER

        return nickname

    _messageRegex = re.compile(r"^([^:]*):(.*)$")

    def _getNumberAndBody(self, toAddress, body):
        """ Get the to phone number and the message body from a message.
        
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
                    strippedNumber = stripNumber(match.group(1))
                    if not (len(strippedNumber) >= 6 and len(strippedNumber) <= 14):
                        errorMessage = "Invalid number."
                    else:
                        if len(strippedNumber) == 10:
                            # Assume a North-American number
                            strippedNumber = "1" + strippedNumber
                        body = match.group(2).strip()
                        toNumber = "+" + strippedNumber
                    
        else:
            # Reverse lookup in config.NICKNAMES
            for number in config.NICKNAMES.keys():
                if config.NICKNAMES[number].lower() == toNickname.lower():
                    toNumber = "+" + stripNumber(number)
                    break

            if not toNumber:
                errorMessage = "Unknown nickname: " + toNickname

        return (toNumber, body, errorMessage)


    def getNumberAndBodyFromEmail(self, emailMessage, messageBody):
        return self._getNumberAndBody(emailMessage.to, messageBody)


    def getNumberAndBodyFromMessage(self, xmppMessage):
        return self._getNumberAndBody(xmppMessage.to.split("/")[0], xmppMessage.body)


xmppVoiceMail = XmppVoiceMail()

class MainHandler(webapp2.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('Hello World!')


class CallHandler(webapp2.RequestHandler):
    # Handles an incoming voice call from Twilio.
    def post(self):
        From = self.request.get("From")
        CallStatus = self.request.get("CallStatus")

        logging.info("Call from: "+From+" status:"+CallStatus)
        xmppVoiceMail.sendXMPPMessage("Call from: "+From+" status:"+CallStatus)

        path = os.path.join(os.path.dirname(__file__), 'receivecall.xml')
        template_vars = {"callbackurl": "/recording"}
        self.response.out.write(template.render(path, template_vars))


class PostRecording(webapp2.RequestHandler):
    def post(self):
        recordingUrl = self.request.get("RecordingUrl")
        transcriptionStatus = self.request.get("TranscriptionStatus")
        caller = self.request.get("Caller")
        transcriptionText = self.request.get("TranscriptionText")

        body = "New message: (" + caller + "): " + transcriptionText + "Recording:" + recordingUrl

        result = xmppVoiceMail.sendMessageToUser(body, config.DEFAULT_SENDER)

        if(result):
            self.response.out.write('')


class SMSHandler(webapp2.RequestHandler):
    # Handles an incoming SMS message from Twilio.
    def get(self):
        self.post()

    def post(self):
        fromNumber = self.request.get("From")
        toNumber = self.request.get("To")
        body = self.request.get("Body")

        # Find the XMPP user to send this from
        nickname = xmppVoiceMail.getNicknameForNumber(fromNumber)
        if nickname == config.DEFAULT_SENDER:
            body = "" + toPrettyNumber(fromNumber) + ": " + body

        xmppVoiceMail.sendMessageToUser(body, nickname)

        self.response.out.write("")


class InviteHandler(webapp2.RequestHandler):
    def get(self):
        self.post()

    def post(self):
        self.response.out.write('<html><body>')

        for nickname in config.NICKNAMES.values():
            fromJid = nickname + "@" + config.XMPP_DOMAIN
            xmpp.send_invite(config.USERJID, fromJid)
            self.response.out.write('Sent invitation for ' + fromJid + "<br/>")

        fromJid = config.DEFAULT_SENDER + "@" + config.XMPP_DOMAIN
        xmpp.send_invite(config.USERJID, fromJid)
        self.response.out.write('Sent invitation for ' + fromJid + "<br/>")

        self.response.out.write('</body></html>')


class FakeXMPPMessage:
    def __init__(self, sender, to, body):
        self.sender = sender
        self.to = to
        self.body = body

class XMPPHandler(webapp2.RequestHandler):
    def _handleXmppMessage(self, message):
        # Handle an XMPP message.
        
        # Make sure the message is from config.USERJID, to stop third
        # parties from using this to spam.
        user = message.sender.split('/')[0]

        if not user == config.USERJID:
            logging.error("Received XMPP message from " + user)

        else:
            toNumber, body, errorMessage = xmppVoiceMail.getNumberAndBodyFromMessage(message)

            if errorMessage or (not toNumber):
                # Reply via XMPP to let the sender know we can't route this message
                xmppVoiceMail.sendXMPPMessage(
                    "ERROR: " + errorMessage,
                    fromJid=(config.DEFAULT_SENDER) +  "@" + config.XMPP_DOMAIN)

            else:
                # Send the message to the SMS number
                xmppVoiceMail.sendSMS(toNumber, body)

    def get(self):
        to = self.request.get("To")
        body = self.request.get("Body")
        sender = self.request.get("Sender")
        message = FakeXMPPMessage(sender, to, body)
        self._handleXmppMessage(message)

    def post(self):
        message = xmpp.Message(self.request.POST)
        self._handleXmppMessage(message)

class XmppPresenceHandler(webapp2.RequestHandler):
    def post(self, available):
        userJid = self.request.get('from').split('/')[0]
        userAvailable = (available == 'available')

        if userJid != config.USERJID:
            logging.warn("Got XMPP presence for unknown user " + userJid)
        else:
            if userAvailable:
                logging.info("User " + userJid + " became available.")
            else:
                logging.info("User " + userJid + " went away.")

            # Update the user in the DB.
            user = XmppUser.getFromJid(userJid)
            if not user:
                logging.info("Creating DB entry for " + userJid)
                user = XmppUser(jid=userJid, presence=userAvailable)
            else:
                user.presence = userAvailable

            user.put()


class MailHandler(InboundMailHandler):
    def receive(self, mail_message):
        if not config.USER_EMAIL in mail_message.sender:
            logging.warn("Got email from unknown user " + mail_message.sender)
        else:
            logging.info("Received an email from: " + mail_message.sender)

            messageBody = ""
            for content_type, body in mail_message.bodies():
                messageBody += body.decode()
                if messageBody:
                    break

            logging.info("Message body: " + messageBody)

            toNumber, body, errorMessage = \
                xmppVoiceMail.getNumberAndBodyFromEmail(mail_message, messageBody)

            if errorMessage or (not toNumber):
                # Reply via XMPP to let the sender know we can't route this message
                mail.send_mail(
                    sender=config.DEFAULT_SENDER,
                    to=config.USER_EMAIL,
                    subject="ERROR: " + errorMessage,
                    body="Original message:\n" + messageBody)
            else:
                xmppVoiceMail.sendSMS(toNumber, body)


def handle_404(request, response, exception):
    logging.exception(exception)
    response.write('Oops! I could swear this page was here!')
    response.set_status(404)

def handle_500(request, response, exception):
    logging.exception(exception)
    response.write('A server error occurred!')
    response.set_status(500)
        
def main():
    routes = [
        (r'/', MainHandler),
        (r'/recording', PostRecording),
        (r'/call', CallHandler),
        (r'/sms', SMSHandler),
        (r'/invite', InviteHandler),
        (r'/_ah/xmpp/message/chat/', XMPPHandler),
        (r'/_ah/xmpp/presence/(available|unavailable)/', XmppPresenceHandler),
        MailHandler.mapping(),
    ]

    webapp2Config = {}
    webapp2Config['webapp2_extras.sessions'] = {
        'secret_key': config.SESSION_SECRET_KEY,
    }
            
    app = webapp2.WSGIApplication(routes=routes, debug=True, config=webapp2Config)
    app.error_handlers[404] = handle_404
    app.error_handlers[500] = handle_500

    return app

app = main()


