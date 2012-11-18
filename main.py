#
# Original Author: Mick Thompson (dthompson@gmail.com)
# Heavily hacked up by: Jason Walton
#
import logging
import os
import json

import webapp2
from webapp2_extras import sessions
from webob.exc import HTTPUnauthorized, HTTPForbidden, HTTPException

from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import xmpp, app_identity
from google.appengine.ext import db

import phonenumberutils
from xmppvoicemail import XmppVoiceMail, Owner
from models import XmppUser, Contact
import errors

import config

owner = Owner(config.TWILIO_NUMBER, config.USERJID, config.USER_EMAIL)
xmppVoiceMail = XmppVoiceMail(owner)

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
    # Handle incoming voide mail from Twilio.
    def post(self):
        recordingUrl = self.request.get("RecordingUrl")
        # transcriptionStatus = self.request.get("TranscriptionStatus")
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


class XMPPHandler(webapp2.RequestHandler):
    # Handle an incoming XMPP message
    def post(self):
        message = xmpp.Message(self.request.POST)
        xmppVoiceMail.handleIncomingXmpp(message)


class XmppPresenceHandler(webapp2.RequestHandler):
    # Tracks presence of XMPP user
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
            user = XmppUser.getByJid(userJid)
            if not user:
                logging.info("Creating DB entry for " + userJid)
                user = XmppUser(jid=userJid, presence=userAvailable)
            else:
                user.presence = userAvailable

            user.put()
            
class XmppSubscribeHandler(webapp2.RequestHandler):
    def post(self, subscriptionType):
        sender = self.request.get('from').split('/')[0]
        to = self.request.get('to').split('/')[0]

        logging.info("Got subscription type " + subscriptionType + " from " + sender + " to " + to)
        
        contactName = to.split('@')[0]
        
        contact = Contact.getByName(contactName)
        if not contact:
            logging.error("Got subscription for unknown contact " + to)
        else:
            if subscriptionType.startswith("un"):
                contact.subscribed = False
            else:
                contact.subscribed = True
            contact.put()

class BaseApiHandler(webapp2.RequestHandler):
    def handle_exception(self, exception, debug):
        if isinstance(exception, errors.ValidationError):
            self.response.out.write(json.dumps({"errorType": exception.__class__.__name__, "error": exception.value}));
            self.response.set_status(400)
        
        elif isinstance(exception, HTTPException):
            self.response.out.write(json.dumps({"errorType": exception.__class__.__name__, "error": exception.title}));
            self.response.set_status(exception.code)
        
        else:
            logging.exception(exception)
            self.response.out.write(json.dumps({"errorType": exception.__class__.__name__, "error": "derp"}));
            self.response.set_status(500)

class LoginHandler(BaseApiHandler):
    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)

        try:        
            super(BaseApiHandler, self).dispatch()
        finally:
            self.session_store.save_sessions(self.response)


class AuthenticatedApiHandler(BaseApiHandler):
    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)

        # TODO: Verify the user is validated        

        try:        
            super(BaseApiHandler, self).dispatch()
        finally:
            self.session_store.save_sessions(self.response)
        
class AdminContactsHandler(AuthenticatedApiHandler):
    # Handle REST API calls for contacts    
    def get(self):
        answer = []

        # Always put the default sender at the top.
        defaultSender = Contact.getDefaultSender()
        answer.append(defaultSender.toDict())

        contacts = Contact.all()
        contacts.filter('__key__ !=', defaultSender.key())
        
        for contact in contacts:
            answer.append(contact.toDict())
            
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(answer))
        
    def post(self):
        user = json.loads(self.request.body)

        logging.info("Got POST for user " + user["name"])

        if not phonenumberutils.validateNumber(user['phoneNumber']):
            raise errors.ValidationError("Invalid phone number.")
            #return validationError(self.response, 'Invalid number ' + user['phoneNumber'])
        
        if not user['name']:
            raise errors.ValidationError("Name is required.")
        
        # Make sure we're not duplicating another contact
        existingContact = Contact.getByName(user['name'])
        if existingContact:
            raise errors.ValidationError('User already exists with name ' + user['name'])
        
        existingContact = Contact.getByPhoneNumber(user['phoneNumber'])
        if existingContact:
            raise errors.ValidationError('User ' + existingContact.name +
              ' already exists with number ' + existingContact.phoneNumber)

        contact = Contact(
            name = user['name'].lower(),
            phoneNumber = phonenumberutils.toPrettyNumber(user['phoneNumber']),
            normalizedPhoneNumber = phonenumberutils.toNormalizedNumber(user['phoneNumber']))
        
        contact.save()

        xmppVoiceMail.sendXmppInvite(contact.name)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(contact.toDict()))

    def delete(self, contactIdStr):
        contact = Contact.getByIdString(contactIdStr)
        if not contact:
            logging.info("Got DELETE for unknown user " + contactIdStr)
        else:
            if contact.isDefaultSender():
                raise errors.ValidationError("Cannot delete default sender.")
            logging.info("Got DELETE for user " + contact.name)
            contact.delete()
        
    # TODO: put for edits.
        

class InviteHandler(webapp2.RequestHandler):
    # TODO: Handle XMPP subscriptions better - convert this to an API handler and add a button to the UI to call it.
    def get(self):
        self.post()

    def post(self):
        self.response.out.write('<html><body>')

        appId = app_identity.get_application_id()
        
        contacts = Contact.all()
        for contact in contacts:
            fromJid = contact.name + "@" + appId + ".appspotchat.com"
            xmpp.send_invite(config.USERJID, fromJid)
            self.response.out.write('Sent invitation for ' + fromJid + "<br/>")

        self.response.out.write('</body></html>')
        

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
        (r'/recording', PostRecording),
        (r'/call', CallHandler),
        (r'/sms', SMSHandler),
        (r'/invite', InviteHandler),
        (r'/api/admin/contacts', AdminContactsHandler),
        (r'/api/admin/contacts/(.*)', AdminContactsHandler),
        
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

    # Send an invite for the default sender if one hasn't been sent.
    defaultSender = Contact.getDefaultSender()
    if not defaultSender.subscribed:
        appId = app_identity.get_application_id()
        fromJid = defaultSender.name + "@" + appId + ".appspotchat.com"
        xmpp.send_invite(config.USERJID, fromJid)
       
    return app

app = main()


