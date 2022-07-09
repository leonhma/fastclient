'''an example package'''

bar = False
'''an example of an module level variable'''


class Foo():
    '''an example class

    Args:
        test (str, optional): some string

    Attributes:
        test (str): some string

    Note:
        lorem ipsum dolor sit amet, consectetur adipiscing el
    '''

    def __init__(self, test):
        self.test = test

    def destroy(self):
        '''remove the test attribute'''
        del self.test
