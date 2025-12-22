from zephil.jlinkboard import JLinkBoard

class FRDMRW612(JLinkBoard):
    def __init__(self, transport, *args, **kwargs):
        super().__init__('RW612', transport, *args, **kwargs)