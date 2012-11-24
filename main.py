#
# Original Author: Mick Thompson (dthompson@gmail.com)
# Heavily hacked up by: Jason Walton (dev@lucid.thedreaming.org)
#
import logging
import os
import json
import sys
import time

import webapp2
from webapp2_extras import sessions
from webob.exc import HTTPUnauthorized, HTTPForbidden, HTTPException

from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import xmpp, app_identity

from util import phonenumberutils
from xmppvoicemail import XmppVoiceMail, Owner, XmppVoiceMailException, PermissionException, InvalidParametersException
from models import XmppUser, Contact
import errors

import config

owner = Owner(config.TWILIO_NUMBER, config.USERJID, config.USER_EMAIL, config.LOG_SIZE)
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


class MailHandler(InboundMailHandler):
    def receive(self, mail_message):
        try:
            sender = mail_message.sender
            to = mail_message.to
            subject = mail_message.subject
    
            # Extract the first message body we can find.
            messageBody = ""
            for content_type, body in mail_message.bodies():
                messageBody += body.decode()
                if messageBody:
                    break

            xmppVoiceMail.handleIncomingEmail(sender, to, subject, messageBody)
            
        except InvalidParametersException as e:
            xmppVoiceMail.sendEmailMessageToOwner("Re:" + subject, e.value)
            
        except PermissionException as e:
            logging.error(str(e))
            
class XMPPHandler(webapp2.RequestHandler):
    # Handle an incoming XMPP message
    def post(self):
        message = xmpp.Message(self.request.POST)

        try:
            sender = message.sender.split('/')[0]
            to = message.to.split("/")[0]
            messageBody = message.body
            xmppVoiceMail.handleIncomingXmpp(sender, to, messageBody)

        except XmppVoiceMailException as e:
            # Reply back letting the sender know what went wrong.
            message.reply(e.value)
        except:
            logging.exception(sys.exc_info()[0])
            message.reply("Unexpected error:" + str(sys.exc_info()[0]))


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
                logging.info("Creating DB entry for user " + userJid)
                user = XmppUser(jid=userJid, presence=userAvailable)
            else:
                user.presence = userAvailable

            user.put()
            
class XmppSubscribeHandler(webapp2.RequestHandler):
    def post(self, subscriptionType):
        sender = self.request.get('from').split('/')[0]
        to = self.request.get('to').split('/')[0]

        contactName = to.split('@')[0]
        
        contact = Contact.getByName(contactName)
        if not contact:
            logging.error("Got subscription type " + subscriptionType + " for unknown contact " + to)
        else:
            logging.info("Got subscription type " + subscriptionType + " from " + sender + " to " + to)        
            if subscriptionType.startswith("un"):
                contact.subscribed = False
            else:
                contact.subscribed = True
            Contact.update(contact)

class BaseApiHandler(webapp2.RequestHandler):
    def handle_exception(self, exception, debug):
        if isinstance(exception, errors.ValidationError) or isinstance(exception, errors.BadPasswordError):
            self.response.out.write(json.dumps({"errorType": exception.__class__.__name__, "error": exception.value}));
            self.response.set_status(400)
        
        elif isinstance(exception, HTTPException):
            self.response.out.write(json.dumps({"errorType": exception.__class__.__name__, "error": exception.title}));
            self.response.set_status(exception.code)
        
        else:
            logging.exception(exception)
            self.response.out.write(json.dumps({"errorType": exception.__class__.__name__, "error": "derp"}));
            self.response.set_status(500)

    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

class LoginHandler(BaseApiHandler):
    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)

        try:        
            super(BaseApiHandler, self).dispatch()
        finally:
            self.session_store.save_sessions(self.response)
            
    def post(self):
        password = self.request.get("password")
        if config.ADMIN_PASSWORD == 'secret':
            # User hasn't changed their admin password yet.  :(
            raise errors.ValidationError("You must change your password in config.py and re-deploy the app.")
        elif password == config.ADMIN_PASSWORD:
            self.session['user'] = True
        else:
            raise errors.BadPasswordError("Incorrect password.")

class AuthenticatedApiHandler(BaseApiHandler):
    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)

        # TODO: Verify the user is validated        
        if not "user" in self.session:
            raise HTTPUnauthorized()

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


        logging.info("Creating contact " + user["name"])
        contact = Contact(
            name = user['name'].lower(),
            phoneNumber = phonenumberutils.toPrettyNumber(user['phoneNumber']),
            normalizedPhoneNumber = phonenumberutils.toNormalizedNumber(user['phoneNumber']))

        Contact.update(contact)

        xmppVoiceMail.sendXmppInvite(contact.name)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(contact.toDict()))

    def delete(self, contactIdStr):
        contact = Contact.getByIdString(contactIdStr)
        if contact:
            if contact.isDefaultSender():
                raise errors.ValidationError("Cannot delete default sender.")
            logging.info("Deleting contact " + contact.name)
            contact.delete()
        
    # TODO: Add put support for edits.
        
class AdminLogHandler(AuthenticatedApiHandler):
    # Handle REST API calls for log entries    
    def get(self):
        logItems = xmppVoiceMail.getLog()
        logItemsJson = [logItem.toDict() for logItem in logItems]
        answer = {
            "now": time.mktime(time.gmtime()) * 1000,
            "logItems": logItemsJson
        }
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(answer))


class InviteHandler(AuthenticatedApiHandler):
    """ Sends invites for all selected users. """
    def post(self):
        appId = app_identity.get_application_id()

        idsToInvite = json.loads(self.request.body)
        invited = []
        for contactId in idsToInvite:
            contact = Contact.getByIdString(contactId)
            fromJid = contact.name + "@" + appId + ".appspotchat.com"
            xmpp.send_invite(config.USERJID, fromJid)
            invited.append(fromJid)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(invited))


class SendSmsHandler(AuthenticatedApiHandler):
    """ Sends an SMS from our xmppVoiceMail. """
    def post(self):
        data = json.loads(self.request.body)
        
        if not data['message']:
            raise errors.ValidationError("Please enter a message.")
            
        toNumber = None
        contact = Contact.getByName(data['to'])
        if contact:
            toNumber = contact.normalizedPhoneNumber
        else:
            if not phonenumberutils.validateNumber(data['to']):
                raise errors.ValidationError("Invalid phone number.")
            else:
                toNumber = phonenumberutils.toNormalizedNumber(data['to'])
        
        xmppVoiceMail.sendSMS(contact, toNumber, data['message'])

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps({'message': 'sent'}))

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
        
        (r'/api/login', LoginHandler),
        (r'/api/admin/contacts', AdminContactsHandler),
        (r'/api/admin/contacts/(.*)', AdminContactsHandler),
        (r'/api/admin/log', AdminLogHandler),
        (r'/api/invite', InviteHandler),
        (r'/api/sendSms', SendSmsHandler),
        
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


