import threading

from google.appengine.api import memcache

#TODO: Add some way to check if anything's been added since the last call to getItems?

class ThreadSafeCircularBuffer:
    """ Stores data in a circular buffer. 
    
    Data is stored in memory, protected by a threading.Lock.
    """

    def __init__(self, bufferSize):
        self._lock = threading.Lock()
        self._bufferSize = bufferSize
        self._buffer = []
        self._head = -1
        
    def addItem(self, item):
        """ Add an item to the circular buffer. """
        with self._lock:
            if self._bufferSize > 0:
                self._head = (self._head + 1) % self._bufferSize
                if len(self._buffer) <= self._head:
                    self._buffer.append(item)
                else:
                    self._buffer[self._head] = item
                
    def getItems(self): 
        """ Return all the items in the buffer, in the same order they were added. """
        answer = []
        with self._lock:
            if self._bufferSize > 0:
                if len(self._buffer) < self._bufferSize:
                    for index in range(0, len(self._buffer)):
                        answer.append(self._buffer[index])
                else:
                    for index in range(1, self._bufferSize + 1):
                        item = self._buffer[index % self._bufferSize]
                        answer.append(item)
                    
        return answer
    

class MemCacheCircularBuffer:
    """ Stores data in a circular buffer. 
    
    Data is stored in MemCache.
    """
    
    def __init__(self, keyPrefix, bufferSize):
        """ Create a new CircularBuffer.
        
        keyPrefix is the prefix to use when storing data in MemCache.
        bufferSize is the maximum number of elements to allow in the buffer.
        """
        self._keyPrefix = keyPrefix
        self._bufferSize = bufferSize
        self._memcache = memcache.Client()
        
    def addItem(self, item):
        """ Add an item to the circular buffer. """
        newKey = self._memcache.incr(key=self._keyPrefix + ":counter",
                                     initial_value=1,
                                     namespace="CircularBuffer")
        
        # Add the new item
        self._memcache.set(key=self._keyPrefix + ":" + str(newKey),
                           value=item,
                           namespace="CircularBuffer")
        
        # Delete the old item
        keyToDelete = newKey - self._bufferSize
        self._memcache.delete(key=self._keyPrefix + ":" + str(keyToDelete),
                              namespace="CircularBuffer")
        
    def getItems(self, maxItemsToGet=None):
        """ Returns all the items in the buffer.
        
        If maxItemsToGet is specified, then at most maxItemsToGet will be
        retrieved from the buffer.
        
        Note that if an item is in the process of being added, this may return
        bufferSize - 1 items and fail to return the new item.
        """
        
        answer = []

        latestKey = self._memcache.get(key=self._keyPrefix + ":counter", namespace="CircularBuffer")
        if latestKey:
            keyValue = int(latestKey[(len(self._keyPrefix) + 1):])
            
            itemCount = self._bufferSize
            if maxItemsToGet:
                itemCount = min(maxItemsToGet, self._bufferSize)
                
            if itemCount:
                end = keyValue + 1
                start = end - itemCount
                
                keysToGet = [(self._keyPrefix + ":" + str(x)) for x in range(start, end)] 
            
                results = self._memcache.get_multi(keysToGet, namespace="CircularBuffer")
                if results:
                    for key in keysToGet:
                        if results[key]:
                            answer.append(results[key])
        
        return answer