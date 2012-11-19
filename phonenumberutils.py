import re

# Adapted from http://blog.stevenlevithan.com/archives/validate-phone-number
_phoneNumberRegex = re.compile(r"^\+?1?[ -]?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$")
_e164Regex = re.compile(r"^\+(?:[0-9] ?){6,14}[0-9]$")

def stripNumber(number):
    return re.sub(r'[^0-9]', "", number)

def toPrettyNumber(phoneNumber):
    match = _phoneNumberRegex.match(phoneNumber)
    if match:
        return "(" + match.group(1) + ")" + match.group(2) + "-" + match.group(3)
    else:
        return phoneNumber

def toNormalizedNumber(phoneNumber):
    normalizedNumber = stripNumber(phoneNumber)
    if len(normalizedNumber) == 10:
        normalizedNumber = "1" + normalizedNumber
    return normalizedNumber

def validateNumber(phoneNumber):
    answer = False
    match = _phoneNumberRegex.match(phoneNumber)
    if match:
        answer = True
    else:
        match = _e164Regex.match(phoneNumber)
        if match:
            answer = True
            
    return answer
