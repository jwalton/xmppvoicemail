from google.appengine.ext import db
from google.appengine.api import memcache

from util import phonenumberutils

_memcache = memcache.Client()

def _getObjectByIdString(clazz, idString):
    if isinstance(idString, int):
        # Already an int
        return clazz.get_by_id(idString)
    
    elif idString.isdigit():
        objectId = int(idString)
        return clazz.get_by_id(objectId)
    
    else:
        return clazz.get_by_key_name(idString)

class XmppUser(db.Model):
    """Tracks presence of user.
    """
    jid = db.StringProperty(required=True)
    presence = db.BooleanProperty(required=True)

    @staticmethod
    def getByJid(jid):
        q = db.GqlQuery("SELECT * FROM XmppUser WHERE jid = :1", jid)
        return q.get()

_DEFAULT_SENDER_MEMCACHE_KEY = 'Contact:DEFAULT_SENDER'
_CONTACT_BY_NUMBER_MEMCACHE_KEY = 'Contact:Number:'
_CONTACT_BY_NAME_MEMCACHE_KEY = 'Contact:Name:'

class Contact(db.Model):
    """Stores information about a contact.
    """
    name = db.StringProperty(required=True)
    """
    Storing phoneNumber and normalizedPhoneNumber violates the DRY principle,
    but there's no way to recover an E.164 number's formatting from the
    normalized number, and it's easier to search by normalized number, so
    here we are.
    """
    phoneNumber = db.StringProperty(required=True)
    normalizedPhoneNumber = db.StringProperty(required=True)
    subscribed = db.BooleanProperty(default=False, required=True)
    
    def toDict(self):
        return {
            "id": self.key().id_or_name(),
            "name": self.name,
            "phoneNumber": self.phoneNumber,
            "subscribed": self.subscribed,
            "isDefaultSender": self.isDefaultSender()
        }
        
    def isDefaultSender(self):
        return self.key().id_or_name() == "DEFAULT_SENDER"
    
    def _addToMemcache(self):
        _memcache.set(_CONTACT_BY_NUMBER_MEMCACHE_KEY + self.normalizedPhoneNumber, self)
        _memcache.set(_CONTACT_BY_NAME_MEMCACHE_KEY + self.name.lower(), self)

    def _removeFromMemcache(self):
        _memcache.delete(_CONTACT_BY_NUMBER_MEMCACHE_KEY + self.normalizedPhoneNumber)
        _memcache.delete(_CONTACT_BY_NAME_MEMCACHE_KEY + self.name.lower())
    
    @staticmethod
    def getByIdString(idString):
        """
        Returns a contact given a string representing it's ID.  If contactIdStr
        can be parsed as number, this will look up the contact using the
        numeric ID.  Otherwise, this will look up the contact using the string
        as a key name.
        """
        return _getObjectByIdString(Contact, idString)
    
    @staticmethod
    def getByPhoneNumber(phoneNumber):
        normalizedNumber = phonenumberutils.toNormalizedNumber(phoneNumber)

        # First try to get from memcache
        answer = _memcache.get(_CONTACT_BY_NUMBER_MEMCACHE_KEY + normalizedNumber)

        if not answer:
            # Fall back to the DB
            q = db.GqlQuery("SELECT * FROM Contact WHERE normalizedPhoneNumber = :1", normalizedNumber)
            answer = q.get()
            if answer:
                answer._addToMemcache()
                
        return answer
        
    @staticmethod
    def getByName(name):
        # First try to get from memcache
        answer = _memcache.get(_CONTACT_BY_NAME_MEMCACHE_KEY + name.lower())
        
        if not answer:
            # Fall back to the DB
            q = db.GqlQuery("SELECT * FROM Contact WHERE name = :1", name.lower())
            answer = q.get()
            if answer:
                answer._addToMemcache()
                
        return answer
    
    @staticmethod
    def update(contact):
        """ Update or create a Contact in the datastore. """
        if contact.isDefaultSender():
            _memcache.set(key=_DEFAULT_SENDER_MEMCACHE_KEY, value=contact)
            # Update the contact in the DB
            contact.put()
                    
        else:
            # Fetch the old contact from the DB
            oldContact = Contact.get(contact.key())
            
            # Update the contact in the DB
            contact.normalizedPhoneNumber = phonenumberutils.toNormalizedNumber(contact.phoneNumber) 
            contact.put()
            
            # Remove the old contact from memcache
            if oldContact:
                oldContact._removeFromMemcache()
                
            # Put the new contact into memcache
            contact._addToMemcache()
            
            
    
    @staticmethod
    def getDefaultSender():
        # TODO: Think about using some caching here, since we get this guy
        # all the time.
        defaultSender = _memcache.get(_DEFAULT_SENDER_MEMCACHE_KEY)
        if defaultSender is not None:
            return defaultSender
        else:
            defaultSender = Contact.get_or_insert("DEFAULT_SENDER",
                name="xmppVoiceMail".lower(),
                phoneNumber="*",
                normalizedPhoneNumber="*")
            _memcache.add(key=_DEFAULT_SENDER_MEMCACHE_KEY, value=defaultSender)
            return defaultSender
        
