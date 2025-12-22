from pytest_hil.board import Board
from pytest_hil.jlinkboard import JLinkBoard

class FRDMRW612(Board, JLinkBoard):
    def __init__(self, *args, **kwargs):
        JLinkBoard.__init__(self, 'RW612')
        Board.__init__(self, *args, **kwargs)