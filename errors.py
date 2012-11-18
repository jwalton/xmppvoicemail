from webob.exc import HTTPBadRequest 
        
class ValidationError(HTTPBadRequest):
    def __init__(self, value):
        super(ValidationError, self).__init__(value)
        self.value = value

