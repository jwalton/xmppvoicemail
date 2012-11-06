#
# Original Author: Mick Thompson (dthompson@gmail.com)
# Heavily hacked up by: Jason Walton
#
import logging
import os

import webapp2
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import xmpp

from xmppvoicemail import XmppVoiceMail, Owner
from models import XmppUser

import config

owner = Owner(config.TWILIO_NUMBER, config.USERJID, config.USER_EMAIL)
xmppVoiceMail = XmppVoiceMail(owner)

class MainHandler(webapp2.RequestHandler):
    def get(self):
        # TODO: Do something useful.
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('Hello World!')


class CallHandler(webapp2.RequestHandler):
    # Handles an incoming voice call from Twilio.
    def post(self):
        fromNumber = self.request.get("from")
        callStatus = self.request.get("CallStatus")

        xmppVoiceMail.handleIncomingCall(fromNumber, callStatus)

        path = os.path.join(os.path.dirname(__file__), 'templates/receivecall.xml')
        template_vars = {"callbackurl": "/recording"}
        self.response.out.write(template.render(path, template_vars))


class PostRecording(webapp2.RequestHandler):
    def post(self):
        recordingUrl = self.request.get("RecordingUrl")
        transcriptionStatus = self.request.get("TranscriptionStatus")
        fromNumber = self.request.get("Caller")
        transcriptionText = self.request.get("TranscriptionText")

        result = xmppVoiceMail.handleVoiceMail(fromNumber, transcriptionText, recordingUrl)

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
        
        xmppVoiceMail.handleIncomingSms(fromNumber, toNumber, body)

        self.response.out.write("")


class InviteHandler(webapp2.RequestHandler):
    # TODO: Handle XMPP subscriptions better
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


class XMPPHandler(webapp2.RequestHandler):
    # Handle an incoming XMPP message
    def post(self):
        message = xmpp.Message(self.request.POST)
        xmppVoiceMail.handleIncomingXmpp(message)


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


class XmppSubscribeHandler(webapp2.RequestHandler):
    def post(self, subscriptionType):
        sender = self.request.get('from').split('/')[0]

        logging.info("Got subscription type " + subscriptionType + " for " + sender)


class MailHandler(InboundMailHandler):
    def receive(self, mail_message):
        xmppVoiceMail.handleIncomingEmail(mail_message)


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
        (r'/_ah/xmpp/subscription/(subscribe|subscribed|unsubscribe|unsubscribed)/', XmppSubscribeHandler),
        
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


