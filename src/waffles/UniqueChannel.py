class UniqueChannel:

    """
    This class implements a unique channel, in the sense
    that its endpoint and channel number is identified.

    Attributes
    ----------
    Endpoint : int
        An endpoint value
    Channel : int
        A channel value

    Methods
    ----------
    ## Add the list of methods and a summary for each one here
    """

    def __init__(self,  endpoint,
                        channel):
        
        """
        UniqueChannel class initializer
        
        Parameters
        ----------
        endpoint : int
        channel : bool
        """

        ## Shall we add type checks here?

        self.__endpoint = endpoint
        self.__channel = channel

    #Getters
    @property
    def Endpoint(self):
        return self.__endpoint
    
    @property
    def Channel(self):
        return self.__channel