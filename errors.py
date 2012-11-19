from webob.exc import HTTPBadRequest 
        
class BadPasswordError(HTTPBadRequest):
    def __init__(self, value):
        super(BadPasswordError, self).__init__(value)
        self.value = value
        
class ValidationError(HTTPBadRequest):
    def __init__(self, value):
        super(ValidationError, self).__init__(value)
        self.value = value
