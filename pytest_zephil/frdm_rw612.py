from pytest_zephil.jlinkboard import JLinkBoard

class FRDMRW612(JLinkBoard):
    def __init__(self, *args, **kwargs):
        super().__init__('RW612', *args, **kwargs)