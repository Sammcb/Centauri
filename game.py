import time
import sys
import shutil
import tty
import termios
import threading
from enum import IntEnum

## MARK: Constants ##
LOG_COLS, LOG_ROWS = shutil.get_terminal_size()
CPU = 'GALILEO'
CMDS = {'?': 'Print the help page', 'log': 'Read the on-suit log book', 'map': 'View the ship maps', 'look': 'Look around the room', 'examine': 'Interact with an object in the room', 'use': 'Use an object from the inventory/see inventory', 'up': 'Move up one room', 'down': 'Move down one room', 'left': 'Move left one room', 'right': 'Move right one room', 'save': 'Save the game', 'quit': 'Quit the game'}
SHIP = [
	[None, 0, None],
	[1, 2, 3],
	[4, 5, 6],
	[7, None, 8]
]
OXY_MAX = 10
ENG_MAX = 10

## MARK: Text customization ##
class TextStyles(IntEnum):
	bold = 1
	faint = 2
	underline = 4
	blink = 5
	reverse = 7

class TextColors(IntEnum):
	title = 14
	cpu_name = 10
	cpu = 11
	p_name = 12
	p_head = 7
	danger = 9
	oxy = 69
	eng = 46
	r0 = 21
	r1 = 69
	r2 = 240
	r3 = 208
	r4 = 76
	r5 = 248
	r6 = 200
	r7 = 92
	r8 = 80

class Text:
	def __init__(self, text='', styles=None, fg=None, bg=None, slow=False, delay=0.05, center=False, row=None, col=None, end=True):
		self.text = text + ('\n' if end else '')
		self.styles = styles if styles else []
		self.fg = fg
		self.bg = bg
		self.slow = slow
		self.delay = delay
		self.center = center
		self.row = row
		self.col = None if center else col

	def mods(self):
		mods = '\x1b[{0}H'.format(self.row) if self.row else ''
		mods += '\x1b[{0}G'.format(self.col) if self.col else ''
		mods += '\x1b[{0}G'.format(LOG_COLS // 2 + 1 - len(self.text) // 2) if self.center else ''
		mods += ''.join(['\x1b[{0}m'.format(style) for style in self.styles])
		mods += '\x1b[38;5;{0}m'.format(self.fg) if self.fg else ''
		mods += '\x1b[48;5;{0}m'.format(self.bg) if self.bg else ''
		return mods

## MARK: Global variables ##
logs = []
name = ''
oxy = OXY_MAX
eng = ENG_MAX
p_room = 0
inventory = []

## MARK: Convenience functions ##
wait = lambda s: time.sleep(0) #s

def getch():
	fd = sys.stdin.fileno()
	old_settings = termios.tcgetattr(fd)
	try:
		tty.setraw(sys.stdin.fileno())
		ch = sys.stdin.read(1)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	return ch

## MARK: Cursor position ##
class PosThread(threading.Thread):
	def __init__(self):
		self.cursor_pos = ''
		threading.Thread.__init__(self)

	def run(self):
		fd = sys.stdin.fileno()
		old_settings = termios.tcgetattr(fd)
		try:
			tty.setraw(sys.stdin.fileno())
			ch = sys.stdin.read(1)
			while(ch != 'R'):
				ch = sys.stdin.read(1)
				self.cursor_pos += ch
		finally:
			termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def cursor_pos():
	print('\x1b7', end='')
	thread = PosThread()
	thread.start()
	print('\x1b[6n\x1b[F')
	thread.join()
	print('\x1b8', end='')
	return [int(coord) for coord in thread.cursor_pos[1:-1].split(';')]

## MARK: Printing to console ##
def n_text(text):
	text_lines = text.text.split('\n')
	for i, line in enumerate(text_lines):
		if len(line) > LOG_COLS - 3:
			end_space = line.rfind(' ', 0, LOG_COLS)
			if end_space >= 0:
				text_lines[i] = line[:end_space] + '\n' + line[end_space + 1:]
			else:
				text_lines[i] = line[:LOG_COLS - 3] + '\n' + line[LOG_COLS - 3:]
	return '\n'.join(text_lines)


def clear_log(r=1):
	print('\x1b[{0}H\x1b[J'.format(r), end='')
	sys.stdout.flush()

def log(text, save=True, clear=False, clear_row=1, validate=True):
	global logs
	if validate:
		c_row, c_col = cursor_pos()
		text.text = n_text(text)
		if c_row + sum([1 for c in text.text if c == '\n']) > LOG_ROWS:
			clear_row = 2
			text.row = 3
			clear = True
	clear_log(clear_row) if clear else None
	print(text.mods(), end='')
	sys.stdout.flush()
	if False: #text.slow
		for c in text.text:
			sys.stdout.write(c)
			sys.stdout.flush()
			wait(text.delay)
	else:
		print(text.text, end='')
	print('\x1b[m', end='')
	sys.stdout.flush()
	if save:
		if clear:
			logs.append(text.mods() + text.text + '\x1b[m')
		else:
			logs[-1] += text.mods() + text.text + '\x1b[m'

class TextBlock:
	def __init__(self, texts=None, save=True, validate=True, extra=1):
		self.texts = texts if texts else []
		self.save = save
		self.validate = validate
		self.extra = extra

	def add_text(self, text):
		self.texts.append(text)

	def write_log(self):
		if self.validate:
			lines = sum([sum([1 for c in n_text(text) if c == '\n']) for text in self.texts])
			c_row, c_col = cursor_pos()
			if c_row + lines > LOG_ROWS - self.extra:
				log(Text(row=3, end=False), clear=True, clear_row=2)
		[log(text, save=self.save, validate=self.validate) for text in self.texts]

def prompt(allowed=[], blocked=[], lower=True, main=True):
	global logs
	c_row, c_col = cursor_pos()
	if c_row + 1 > LOG_ROWS:
		log(Text(row=3, end=False), clear=True)
		print_meters()
	text = input('\x1b7> ' if main else '\x1b7$ ')
	if lower:
		text = text.lower()
	while (allowed and text.strip() not in allowed) or (blocked and text.strip() in blocked) or len(text) > LOG_COLS - 3:
		text = input('\x1b8\x1b[J> ' if main else '\x1b8\x1b[J$ ')
		if lower:
			text = text.lower()
	logs[-1] += '{0} {1}\n'.format('>' if main else '$', text.strip())
	return text.strip()

## MARK: Items ##
class Item():
	def __init__(self, name='', info='', use=None):
		self.name = name
		self.info = info
		self.use = self.__use_error
		self.use = use if use else self.use

	def __use_error():
		raise NotImplementedError

class EnergyPack(Item):
	def __init__(self):
		super().__init__(
			name = 'energy pack',
			info = 'restores 1 energy point',
			use = self.use_energy_pack
		)

	def use_energy_pack(self):
		global eng
		if eng == ENG_MAX:
			TextBlock(texts=[Text('Energy already full!'), spacer()]).write_log()
		else:
			eng += 1
			for i, item in enumerate(inventory):
				if item.name == self.name:
					del inventory[i]
					break

## MARK: Rooms ##
class RoomObj():
	def __init__(self, examine=None):
		self.examine = self.__examine_error
		self.examine = examine if examine else self.examine

	def __examine_error():
		raise NotImplementedError

class Room:
	def __init__(self, name='', info='', new=True, color=TextColors.r0, objects={}):
		self.name = name
		self.info = info
		self.new = new
		self.color = color
		self.objects = objects

class R0(Room):
	def __init__(self, door_locked=True, box_looted=False):
		super().__init__(
			name='Bridge',
			info='The room has a single chair and a console at the front. To the left is an open cryopod. To the right is storage box. Behind is a door.',
			new=False,
			objects={'console': RoomObj(examine=self.examine_console), 'box': RoomObj(examine=self.examine_box), 'door': RoomObj(examine=self.examine_door)}
		)
		self.door_locked=door_locked
		self.box_looted=box_looted

	def examine_console(self):
		console_block = TextBlock()
		console_block.add_text(Text('What would you like to do?'))
		console_block.add_text(Text('a) Read mission history'))
		console_block.add_text(Text('b) Unlock doors'))
		console_block.add_text(Text('c) Close'))
		console_block.write_log()
		option = prompt(allowed=['a', 'b', 'c'], main=False)
		if option == 'a':
			TextBlock(texts=[Text('[[INSERT MISSION HISTORY]]'), spacer()]).write_log()
		elif option == 'b':
			if self.door_locked:
				self.door_locked = False
				TextBlock(texts=[Text('Doors unlocked')], extra=3).write_log()
				log(Text('<You can now move through the ship>', styles=[TextStyles.faint]), save=False)
				log(spacer())
			else:
				TextBlock(texts=[Text('Doors already unlocked.'), spacer()]).write_log()

	def examine_box(self):
		global inventory
		if self.box_looted:
			TextBlock(texts=[Text('The box is empty.'), spacer()]).write_log()
		else:
			self.box_looted = True
			TextBlock(texts=[Text('There is a spare {0} inside the box.'.format('energy pack'))], extra=3).write_log()
			log(Text('<Added {0} to inventory>'.format('energy pack'), styles=[TextStyles.faint]), save=False)
			log(spacer())
			inventory += [EnergyPack()]

	def examine_door(self):
		TextBlock(texts=[Text('The door appears to be locked.' if self.door_locked else 'The door is unlocked.'), spacer()]).write_log()

class R1(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Oxygen Tanks',
			new=new,
			color=TextColors.r1
		)

class R2(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Terraforming Equipment',
			new=new,
			color=TextColors.r2
		)

class R3(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Food Stores',
			new=new,
			color=TextColors.r3
		)

class R4(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Reactor',
			new=new,
			color=TextColors.r4
		)

class R5(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Mainframe',
			new=new,
			color=TextColors.r5
		)

class R6(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Escape Pod',
			new=new,
			color=TextColors.r6
		)

class R7(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Left Engine',
			new=new,
			color=TextColors.r7
		)

class R8(Room):
	def __init__(self, new=True):
		super().__init__(
			name='Right Engine',
			new=new,
			color=TextColors.r8
		)

rooms = [R0(), R1(), R2(), R3(), R4(), R5(), R6(), R7(), R8()]

## MARK: Convenience logs ##
spacer = lambda n=1: Text('\n' * (n - 1))

def next():
	log(Text('<Press any key to continue>', styles=[TextStyles.faint], end=False), save=False)
	getch()

def print_meters():
	print('\x1b7', end='')
	meter_block = TextBlock(save=False, validate=False)
	meter_block.add_text(Text('O2: [', row=1, end=False))
	meter_block.add_text(Text('=' * oxy, fg=TextColors.oxy, end=False))
	meter_block.add_text(Text('] {0}/{1} | \u26A1: ['.format(oxy, OXY_MAX), end=False))
	meter_block.add_text(Text('=' * eng, fg=TextColors.eng, end=False))
	meter_block.add_text(Text('] {0}/{1} | Help (?)'.format(eng, ENG_MAX), end=False))
	meter_block.write_log()
	print('\x1b8', end='')

def to_game(show_meters=True):
	log(Text(logs[-1], end=False), save=False, clear=True, validate=False)
	print_meters() if show_meters else None

def print_logs():
	i = len(logs) - 1
	while True:
		log(Text('Entry [{0}/{1}] | Previous (a) | Next (d) | Quit (q)'.format(str(i + 1).rjust(len(str(len(logs)))), len(logs))), save=False, clear=True, validate=False)
		log(Text(logs[i], end=False), save=False, validate=False)
		ch = getch()
		while ch != 'q' and ch != 'a' and ch != 'd':
			ch = getch()
		if ch == 'q':
			break
		elif ch == 'a':
			i = i - 1 if i > 0 else len(logs) - 1
		else:
			i = i + 1 if i < len(logs) - 1 else 0
	to_game()

def print_map():
	log(Text('--Map-- ', end=False), save=False, clear=True, validate=True)
	log(Text('(press any key to exit)', styles=[TextStyles.faint]), save=False, validate=False)
	map_block = TextBlock(save=False, validate=False)
	for i, row in enumerate(SHIP):
		for n, ri in enumerate(row):
			r = (i + 1) * 3
			c = LOG_COLS // 2 - 3 + 3 * n
			if ri is None:
				map_block.add_text(Text('   ', row=r, col=c))
				map_block.add_text(Text('   ', row=r + 1, col=c))
				map_block.add_text(Text('   ', row=r + 2, col=c))
			else:
				co = rooms[ri].color
				h = ri == p_room
				map_block.add_text(Text(rooms[ri].name, fg=co, row=3 + ri, end=False))
				map_block.add_text(Text('---', bg=co, row=r, col=c))
				map_block.add_text(Text('|', bg=co, row=r + 1, col=c, end=False))
				map_block.add_text(Text('*' if h else ' ', styles=[TextStyles.blink] if h else [], fg=TextColors.danger if h else None, bg=co, row=r + 1, col=c + 1, end=False))
				map_block.add_text(Text('|', bg=co, row=r + 1, col=c + 2))
				map_block.add_text(Text('---', bg=co, row=r + 2, col=c))
	map_block.write_log()
	getch()
	to_game()

def print_help():
	log(Text('--List of commands-- ', end=False), save=False, clear=True, validate=False)
	log(Text('(press any key to exit)', styles=[TextStyles.faint]), save=False, validate=False)
	for cmd, cmd_info in CMDS.items():
		log(Text('{0}'.format(cmd), end=False), save=False, validate=False)
		log(Text(' - {0}'.format(cmd_info)), save=False, validate=False)
	getch()
	to_game()

## MARK: Logic ##
def move(direction):
	global p_room
	if direction == 'down' and rooms[0].door_locked:
		TextBlock(texts=[Text('The door appears to be locked'), spacer()]).write_log()
	else:
		p_loc = ()
		moved = True
		for i in range(len(SHIP)):
			for n in range(len(SHIP[0])):
				if SHIP[i][n] == p_room:
					p_loc = (i, n)
		if direction == 'up' and p_loc[0] != 0 and SHIP[p_loc[0] - 1][p_loc[1]] is not None:
			p_room = SHIP[p_loc[0] - 1][p_loc[1]]
		elif direction == 'down' and p_loc[0] != len(SHIP) - 1 and SHIP[p_loc[0] + 1][p_loc[1]]:
			p_room = SHIP[p_loc[0] + 1][p_loc[1]]
		elif direction == 'left' and p_loc[1] != 0 and SHIP[p_loc[0]][p_loc[1] - 1]:
			p_room = SHIP[p_loc[0]][p_loc[1] - 1]
		elif direction == 'right' and p_loc[1] != len(SHIP[0]) - 1 and SHIP[p_loc[0]][p_loc[1] + 1]:
			p_room = SHIP[p_loc[0]][p_loc[1] + 1]
		else:
			moved = False
		if moved and rooms[p_room].new:
			rooms[p_room].new = False
			TextBlock(texts=[Text(rooms[p_room].info), spacer()]).write_log()
		elif not moved:
			TextBlock(texts=[Text('There is no door that way'), spacer()]).write_log()

def run_cmd(cmd):
	if cmd == '?':
		print_help()
	elif cmd == 'log':
		print_logs()
	elif cmd == 'map':
		print_map()
	elif cmd == 'look':
		TextBlock(texts=[Text(rooms[p_room].info), spacer()]).write_log()
	elif cmd == 'examine':
		examine_block = TextBlock()
		examine_block.add_text(Text('What would you like to examine?'))
		for obj in rooms[p_room].objects.keys():
			examine_block.add_text(Text(obj))
		examine_block.add_text(Text('nothing'))
		examine_block.write_log()
		option = prompt(allowed=list(rooms[p_room].objects.keys()) + ['nothing'], main=False)
		if option != 'nothing':
			rooms[p_room].objects[option].examine()
	elif cmd == 'use':
		use_block = TextBlock()
		use_block.add_text(Text('What would you like to use?'))
		for item in inventory:
			use_block.add_text(Text(item.name, end=False))
			use_block.add_text(Text(' - {0}'.format(item.info), styles=[TextStyles.faint]))
		use_block.add_text(Text('nothing'))
		use_block.write_log()
		option = prompt(allowed=[item.name for item in inventory] + ['nothing'], main=False)
		if option != 'nothing':
			[item.use() for item in inventory if item.name == option]
	elif cmd in ['up', 'down', 'left', 'right']:
		move(cmd)
	elif cmd == 'save':
		pass
	elif cmd == 'quit':
		pass

## MARK: Intro ##
def scan_cutscene():
	for i in range(3, LOG_ROWS - 2):
		log(Text('-' * LOG_COLS, fg=TextColors.danger, row=i, end=False), save=False, clear=True, validate=False)
		wait(0.1)
	for i in range(LOG_ROWS - 2, 3, -1):
		log(Text('-' * LOG_COLS, fg=TextColors.danger, row=i, end=False), save=False, clear=True, validate=False)
		wait(0.1)
	to_game(show_meters=False)

def title_screen():
	log(Text('CENTAURI', styles=[TextStyles.bold, TextStyles.underline], fg=TextColors.title, slow=True, delay=0.2, center=True, row=5, end=False), save=False, clear=True)
	log(Text('Press any key to start', styles=[TextStyles.bold, TextStyles.blink], center=True, row=15), save=False)
	getch()

def start_cutscene():
	global name
	clear_log()
	wait(3)
	log(Text('W A R N I N G', styles=[TextStyles.bold, TextStyles.blink], fg=TextColors.danger, center=True, row=3), clear=True)
	wait(3)
	log(Text('[???]', fg=TextColors.cpu_name, row=6))
	log(Text('Hull breach. Immediate action required.', styles=[TextStyles.bold], fg=TextColors.danger, slow=True))
	log(spacer())
	wait(1)
	log(Text('Prematurely lifting cryosleep protocol', fg=TextColors.cpu, slow=True, end=False))
	log(Text('...', fg=TextColors.cpu, slow=True, delay=1))
	wait(1)
	log(Text('Opening cryopod', fg=TextColors.cpu, slow=True, end=False))
	log(Text('...', fg=TextColors.cpu, slow=True, delay=1))
	log(spacer())
	wait(1)
	log(Text('Good morning, captain. Sorry for the early wake up, but there appears to be an issue with the ship.', fg=TextColors.cpu, slow=True))
	log(spacer())
	wait(1)
	log(Text('[???]', fg=TextColors.p_name))
	log(Text('Ugh. Wh~ what? My head is spinning...', fg=TextColors.p_head))
	next()
	log(Text('[{0}]'.format(CPU), fg=TextColors.cpu_name, row=3), clear=True)
	log(Text('Your memory may be a bit foggy since I had to temporarily abort the cryosleep. I am the ship\'s computer, GALILEO', fg=TextColors.cpu, slow=True))
	log(spacer())
	wait(1)
	log(Text('[???]', fg=TextColors.p_name))
	log(Text('Hmm... I think that sounds familiar... What was my name again?', fg=TextColors.p_head))
	name = prompt(blocked=[''], lower=False)
	wait(1)
	log(Text('Yes! My name is {0}.'.format(name), fg=TextColors.p_head))
	log(spacer())
	wait(1)
	log(Text('[{0}]'.format(CPU), fg=TextColors.cpu_name))
	log(Text('You seem to have more trouble remembering than was expected. This is worrying.', fg=TextColors.cpu, slow=True))
	log(spacer())
	wait(1)
	log(Text('Running health scan', fg=TextColors.cpu, slow=True, end=False))
	log(Text('...', fg=TextColors.cpu, slow=True, delay=1))
	log(spacer())
	scan_cutscene()
	log(Text('Luckily you appear to be physically ok.', fg=TextColors.cpu, slow=True))
	log(spacer())
	wait(1)
	log(Text('I recommend exploring the ship to refamiliarize yourself with the mission.', fg=TextColors.cpu, slow=True))
	next()
	log(Text('[{0}]'.format(CPU), fg=TextColors.cpu_name, row=3), clear=True)
	print_meters()
	log(Text('You might want to press the help button on your suit to see what actions you can perform.', fg=TextColors.cpu, slow=True))
	log(Text('<Press \'?\' to see the list of actions>', styles=[TextStyles.faint]), save=False)
	cmd = prompt(allowed=['?'])
	run_cmd(cmd)

## MARK: Game loop ##
def game_start():
	while True:
		cmd = prompt(allowed=CMDS.keys())
		run_cmd(cmd)

def init():
	title_screen()
	start_cutscene()
	game_start()

init()
