import unittest

from google.appengine.ext import testbed


import util.circularbuffer

class CircularBufferTestCases(unittest.TestCase):

    def setUp(self):
        self.BUFFER_SIZE = 10
        # Set up Google App Engine testbed
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_memcache_stub()
         
    def tearDown(self):
        self.testbed.deactivate()
               
    def test_lessThanSize(self):
        buf = util.circularbuffer.MemCacheCircularBuffer(self.BUFFER_SIZE)
        buf.addItem(1)

        items = buf.getItems()
        self.assertEquals(1, len(items))
        self.assertEquals(1, items[0])

    def test_exactBufferSize(self):
        buf = util.circularbuffer.MemCacheCircularBuffer(self.BUFFER_SIZE)
        for i in range(0, self.BUFFER_SIZE):
            buf.addItem(i)
            
        items = buf.getItems()
        print items
        self.assertEquals(self.BUFFER_SIZE, len(items))
        for i in range(0, self.BUFFER_SIZE):
            self.assertEquals(i, items[i])

    def test_overBufferSize(self):
        buf = util.circularbuffer.MemCacheCircularBuffer(self.BUFFER_SIZE)
        for i in range(0, self.BUFFER_SIZE + 2):
            buf.addItem(i)
            
        items = buf.getItems()
        print items
        self.assertEquals(self.BUFFER_SIZE, len(items))
        for i in range(0, self.BUFFER_SIZE):
            self.assertEquals(i + 2, items[i])

            
if __name__ == '__main__':
    unittest.main()