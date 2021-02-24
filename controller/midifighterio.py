import mido, chess
from queue import Queue

from .midiboard import MIDIBoard
from .constants import *

class MidiFighterIO():
    def __init__(self):
        self.board = MIDIBoard()
        input_name = next(filter(lambda x: x.startswith('Midi Fighter'), mido.get_input_names()))
        output_name = next(filter(lambda x: x.startswith('Midi Fighter'), mido.get_output_names()))
        self.input = mido.open_input(input_name)
        self.output = mido.open_output(output_name)
        # init note-off hex
        print('\n\nPress any key to begin...')
        self.input.receive()
        self.note_off = self.input.receive().hex().split()[0]

    def square_to_coords(self, coord):
        if isinstance(coord, list) or isinstance(coord, tuple):
            return coord
        return (7-(coord//8), coord%8)

    def wait_for_down_press(self):
        button_data = self.input.receive()
        while button_data.hex().startswith(self.note_off):
            button_data = self.input.receive()

    def get_button_press(self):
        # flush
        list(self.input.iter_pending())

        inputs = set()
        button_data = self.input.receive()
        inputs.add(button_data.hex().split()[1])
        while not button_data.hex().startswith(self.note_off):
            button_data = self.input.receive()
            inputs.add(button_data.hex().split()[1])
            if self.resigned(inputs):
                return 'resign'
        return button_data.hex().split()[1]
        
    def resigned(self, input_set):
        # two bottom left and bottom right buttons
        return '24' in input_set and '25' in input_set and '46' in input_set and '47' in input_set;

    def get_square(self):
        button_byte = self.get_button_press()
        if button_byte == 'resign':
            return 'resign'
        return self.square_to_coords(BOARD_BYTE_TO_COORDS[button_byte])

    def build_msg_block(self, lines, half='01'):
        # lines is 8 lines long, please
        # half is '01' or '02', please
        dup_lines = lines * 2
        rows = []
        for j in range(16):
            row_num = hex(j+1).split('x')[1].zfill(2)
            rows.append(MIDI_COLOUR_HEADER + half + row_num + MIDI_COLOUR_DELIM + dup_lines[j] + TERMINATOR)
        return rows

    def get_midi(self):
        lines = []
        for i in range(8):
            data = ''.join([''.join(self.board.get(BOARD_COORDS[i][j])) for j in range(8)])
            lines.append(data)

        block = self.build_msg_block(lines, '01') + self.build_msg_block(lines, '02')
        block.insert(0, DEFAULT_SETTINGS)
        return block

    def send_board_state(self, board):
        # where board is a chess.Board
        bad = set()
        for piece in board.piece_map().items():
            bad.add(piece[0])
            if piece[1].color: # white
                self.board.set(self.square_to_coords(piece[0]), ['7f', '7f', '7f'])
            else:
                self.board.set(self.square_to_coords(piece[0]), ['7b', '00', '3d'])
            if board.is_check() and piece[1].symbol() == 'K':
                self.board.set(self.square_to_coords(piece[0]), ['7f', '7f', '00'])

        for i in range(64):
            if i not in bad:
                # print(i)
                self.board.set(self.square_to_coords(i), ['00', '00', '00'])


        self.push()

    def send_piece_selected(self, board, coords, attacks):
        # dont look at This
        bad = set()
        for piece in board.piece_map().items():
            bad.add(self.square_to_coords(piece[0]))
        for x,y in attacks:
            if ((7-y), x) in bad:
                self.board.set((7-y, x), ['7f', '00', '00'])
            else:
                self.board.set((7-y, x), ['00', '7f', '00'])
        self.board.set((7-coords[0], coords[1]), ['00', '00', '7f'])
        self.push()
    def push(self):
        for midi_line in self.get_midi():
            msg = mido.Message.from_bytes(bytearray.fromhex(midi_line))
            self.output.send(msg)

    def send_loser(self, board, resign=False):
        if resign or board.result() == "0-1":
            for piece in board.piece_map().items():
                if piece[1].color:
                    self.board.set(self.square_to_coords(piece[0]), ['7f', '00', '00'])
        elif board.result() == "1-0":
            for piece in board.piece_map().items():
                if not piece[1].color:
                    self.board.set(self.square_to_coords(piece[0]), ['7f', '00', '00'])
        self.push()
