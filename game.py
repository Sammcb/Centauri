import time
import sys
import shutil
import tty
import termios
import threading
import random
from enum import IntEnum

## MARK: Constants ##
LOG_COLS, LOG_ROWS = shutil.get_terminal_size()
CPU = 'GALILEO'
CMDS = {'?': 'Print the help page', 'log': 'Read the on-suit log book', 'map': 'View the ship maps', 'look': 'Look around the room', 'examine': 'Interact with an object in the room', 'inventory': 'List items in the inventory', 'use': 'Use an object from the inventory', 'up': 'Move up one room', 'down': 'Move down one room', 'left': 'Move left one room', 'right': 'Move right one room', 'save': 'Save the game', 'quit': 'Quit the game'}
SHIP = [
	[None, 0, None],
	[1, 2, 3],
	[4, 5, 6],
	[7, None, 8]
]
FIX_MAX = 3
QUICK_MAX = 1

class GameOverState(IntEnum):
	win = 0
	escape = 1
	lose = 2

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
	enc = 197
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
oxy_max = 10
eng_max = 10
oxy = oxy_max
eng = eng_max
p_room = 0
inventory = []
# fix_rooms = random.sample([1, 2, 3, 4, 5, 6, 7, 8], FIX_MAX)
fix_rooms = [1]
quick_rooms = random.sample([1, 3, 4, 6, 7, 8], QUICK_MAX)

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
				text_lines[i] = line[:end_space] + '\n' + n_text(Text(line[end_space + 1:], end=False))
			else:
				text_lines[i] = line[:LOG_COLS - 3] + '\n' + n_text(Text(line[LOG_COLS - 3:], end=False))
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

def prompt(allowed=[], blocked=[], lower=True, main=True, save=True):
	global logs
	c_row, c_col = cursor_pos()
	if c_row + 1 > LOG_ROWS:
		log(Text(row=3, end=False), clear=True, save=save)
		print_meters()
	text = input('\x1b7> ' if main else '\x1b7$ ')
	if lower:
		text = text.lower()
	while (allowed and text.strip() not in allowed) or (blocked and text.strip() in blocked) or len(text) > LOG_COLS - 3:
		text = input('\x1b8\x1b[J> ' if main else '\x1b8\x1b[J$ ')
		if lower:
			text = text.lower()
	if save:
		logs[-1] += '{0} {1}\n'.format('>' if main else '$', text.strip())
	return text.strip()

spacer = lambda n=1: Text('\n' * (n - 1))

def next():
	log(Text('<Press any key to continue>', styles=[TextStyles.faint], end=False), save=False)
	getch()

def print_meters():
	print('\x1b7', end='')
	meter_block = TextBlock(save=False, validate=False)
	meter_block.add_text(Text('O2: [', row=1, end=False))
	meter_block.add_text(Text('{0}'.format('=' * oxy).ljust(oxy_max), fg=TextColors.oxy, end=False))
	meter_block.add_text(Text('] {0}/{1} | \u26A1: ['.format(oxy, oxy_max), end=False))
	meter_block.add_text(Text('{0}'.format('=' * eng).ljust(eng_max), fg=TextColors.eng, end=False))
	meter_block.add_text(Text('] {0}/{1} | Help (?)'.format(eng, eng_max), end=False))
	meter_block.write_log()
	print('\x1b8', end='')

def to_game(show_meters=True):
	log(Text(logs[-1], end=False), save=False, clear=True, validate=False)
	print_meters() if show_meters else None

## MAKR: Game over ##
def end(state=GameOverState.win):
	if state == GameOverState.win:
		pass
	elif state == GameOverState.escape:
		pass
	elif state==GameOverState.lose:
		log(Text(row=3, end=False), clear=True)
		log(Text('Game Over', styles=[TextStyles.bold, TextStyles.underline], fg=TextColors.danger, center=True))
		log(spacer())
		wait(1)
		log(Text('Your suit ran out of energy, causing the oxygen replenishment systems to cease. You suffocated and the ship crashed due to unsolved issues.'))
		wait(1)
		log(Text('Better luck next time, and thanks for playing!'))
	log(spacer(), save=False, validate=False)
	exit()

## MARK: CPU fight ##
def battle_meters(enc, enc_max):
	print('\x1b7', end='')
	battle_block = TextBlock(save=False, validate=False)
	battle_block.add_text(Text('\u26A1: [', row=1, end=False))
	battle_block.add_text(Text('{0}'.format('=' * eng).ljust(eng_max), fg=TextColors.eng, end=False))
	battle_block.add_text(Text('] {0}/{1} | CPU Encryption: ['.format(eng, eng_max), end=False))
	battle_block.add_text(Text('{0}'.format('=' * enc).ljust(enc_max), fg=TextColors.enc, end=False))
	battle_block.add_text(Text('] {0}/{1}'.format(enc, enc_max), end=False))
	battle_block.write_log()
	print('\x1b8', end='')

def hack_cpu(battle=FIX_MAX - len(fix_rooms)):
	global eng
	intro_block = TextBlock(extra=2)
	intro_block.add_text(Text('[{0}]'.format(name), fg=TextColors.p_name))
	intro_block.add_text(Text('Something must be wrong with GALILEO. I\'ll have to hack into the mainframe and fix the problem.', fg=TextColors.p_head))
	intro_block.add_text(spacer())
	intro_block.add_text(Text('[{0}]'.format(CPU), fg=TextColors.cpu_name))
	intro_block.add_text(Text('Threat detected.', fg=TextColors.danger, slow=True))
	intro_block.add_text(Text('Initializing defence protocol', fg=TextColors.cpu, slow=True, end=False))
	intro_block.add_text(Text('...', fg=TextColors.cpu, slow=True, delay=1))
	if battle == 0:
		enc = enc_max = 3
	elif battle == 1:
		intro_block.add_text(Text('Encryption algorithm V2 loaded.', fg=TextColors.cpu, slow=True))
		enc = enc_max = 5
	elif battle == 2:
		intro_block.add_text(Text('Encryption algorithm V3 loaded.', fg=TextColors.cpu, slow=True))
		enc = enc_max = 7
	elif battle == 3:
		pass # final battle
	intro_block.add_text(spacer())
	intro_block.write_log()
	next()
	p_turn = True
	p_safe = False
	while enc > 0 and eng > 0:
		log(Text(end=False), save=False, clear=True, validate=False)
		battle_meters(enc, enc_max)
		if p_turn:
			p_safe = False
			hack_block = TextBlock(save=False, validate=False)
			hack_block.add_text(Text('What would you like to do?', row=3))
			hack_block.add_text(Text('a) Hack', end=False))
			hack_block.add_text(Text(' <lowers GALILEO\'s encryption by 1 (crit=2) point(s)>', styles=[TextStyles.faint]))
			hack_block.add_text(Text('b) Take hands off keyboard', end=False))
			hack_block.add_text(Text(' <protects against being zapped>', styles=[TextStyles.faint]))
			hack_block.add_text(spacer())
			hack_block.write_log()
			option = prompt(allowed=['a', 'b'], main=False, save=False)
			if option == 'a':
				crit = random.randint(0, 5)
				if crit < 4:
					enc -= 1
					TextBlock(texts=[Text('Decreased encryption by 1 point')], save=False, validate=False, extra=2).write_log()
				else:
					enc -= 2
					TextBlock(texts=[Text('Critical hack!', fg=TextColors.eng, end=False) ,Text(' Decreased encryption by 2 points')], save=False, validate=False, extra=2).write_log()
			else:
				p_safe = True
				TextBlock(texts=[Text('Lifted hands off keyboard')], save=False, validate=False, extra=2).write_log()
		else:
			hack_block = TextBlock(texts=[Text(row=3, end=False)] ,save=False, validate=False, extra=2)
			cpu_action = random.randint(0, 10)
			if cpu_action < 5:
				hack_block.add_text(Text('GALILEO is computing...'))
			elif cpu_action < 8:
				if p_safe:
					hack_block.add_text(Text('The keyboard sparks! Good thing I lifted my hands.'))	
				else:
					eng -= 1
					hack_block.add_text(Text('Ouch!'))
			else:
				enc += 1 if enc < enc_max else 0
				hack_block.add_text(Text('Re-encrypting files...'))
			hack_block.write_log()
		p_turn = not p_turn
		next()
	if eng == 0:
		end(state=GameOverState.lose)
	to_game()

## MARK: Items ##
class Item():
	def __init__(self, use=None):
		self.use = self.__use_error
		self.use = use if use else self.use

	def __use_error():
		raise NotImplementedError

	def remove_item(self):
		global inventory
		for i, item in enumerate(inventory):
			if item.name == self.name:
				del inventory[i]
				break

class EnergyPack(Item):
	name = 'energy pack'
	info = 'restores 1 energy point'

	def __init__(self):
		super().__init__(use=self.use_energy_pack)

	def use_energy_pack(self):
		global eng
		if eng == eng_max:
			TextBlock(texts=[Text('Energy already full!'), spacer()]).write_log()
		else:
			eng += 1
			self.remove_item()

class OxygenPack(Item):
	name = 'oxygen pack'
	info = 'fully restores oxygen'

	def __init__(self):
		super().__init__(use=self.use_oxygen_pack)

	def use_oxygen_pack(self):
		global oxy
		if oxy == oxy_max:
			TextBlock(texts=[Text('Oxygen already full!'), spacer()]).write_log()
		else:
			oxy = oxy_max
			self.remove_item()

## MARK: Rooms ##
class RoomObj():
	def __init__(self, examine=None):
		self.examine = self.__examine_error
		self.examine = examine if examine else self.examine

	def __examine_error(self):
		raise NotImplementedError

class Room:
	def __init__(self, new=True, fix_event=None, quick_event=None, fix_done=True, quick_done=True, objects=None):
		self.new = new
		self.objects = objects if objects else {}
		self.fix_event = self.__fix_event_error
		self.fix_event = fix_event if fix_event else self.fix_event
		self.quick_event = self.__quick_event_error
		self.quick_event = quick_event if quick_event else self.quick_event
		self.fix_done = fix_done
		self.quick_done = quick_done

	def __fix_event_error(self):
		raise NotImplementedError

	def __quick_event_error(self):
		raise NotImplementedError

class R0(Room):
	name='Bridge'
	info='There is a single chair and a console at the front. To the left is a recently opened cryopod. To the right is storage box. Behind is a door.'
	color=TextColors.r0

	def __init__(self, door_locked=True, box_looted=False):
		super().__init__(
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
			TextBlock(texts=[Text('There is a spare {0} inside the box.'.format(EnergyPack.name))], extra=3).write_log()
			log(Text('<Added {0} to inventory>'.format(EnergyPack.name), styles=[TextStyles.faint]), save=False)
			log(spacer())
			inventory += [EnergyPack()]

	def examine_door(self):
		TextBlock(texts=[Text('The door appears to be locked.' if self.door_locked else 'The door is unlocked.'), spacer()]).write_log()

class R1(Room):
	name='Oxygen Tanks'
	info='Large tanks filled with liquid oxygen stretch from floor to ceiling. There is a shelf in the corner with some portable o2 cells. A small terminal on the wall blinks periodically.'
	color=TextColors.r1
	fix_info='There is a hissing sound that can be heard throughout the room. One of the tank valves must have been opened! The terminal might allow me to debug the problem.'

	def __init__(self, new=True, shelf_looted=False, fix_done=True, quick_done=True):
		super().__init__(
			new=new,
			fix_event=self.fix_event,
			quick_event=self.quick_event,
			fix_done=fix_done,
			quick_done=quick_done,
			objects={'shelf': RoomObj(examine=self.examine_shelf), 'terminal': RoomObj(examine=self.examine_terminal)}
		)
		self.shelf_looted = shelf_looted

	def examine_shelf(self):
		global inventory
		if self.shelf_looted:
			TextBlock(texts=[Text('There is nothing on the shelf.'), spacer()]).write_log()
		else:
			self.shelf_looted = True
			TextBlock(texts=[Text('There is an {0} inside the box.'.format(OxygenPack.name))], extra=3).write_log()
			log(Text('<Added {0} to inventory>'.format(OxygenPack.name), styles=[TextStyles.faint]), save=False)
			log(spacer())
			inventory += [OxygenPack()]

	def examine_terminal(self):
		if self.fix_done:
			TextBlock(texts=[Text('A message flashes showing that all systems are operational.'), spacer()]).write_log()
		else:
			log(spacer())
			self.fix_event()

	def fix_event(self):
		hack_cpu()
		fix_rooms.remove(p_room)
		self.fix_done = True
		fix_block = TextBlock()
		fix_block.add_text(Text('[{0}]'.format(name), fg=TextColors.p_name))
		fix_block.add_text(Text('Great, I was able to access the value control systems and stop the leak!', fg=TextColors.p_head))
		fix_block.add_text(spacer())
		fix_block.write_log()

	def quick_event(self):
		pass

class R2(Room):
	name='Terraforming Equipment'
	info='Massive containers line the back wall filled with nutrient-rich soil, water, and seeds of various crops. The rest of the 1km long room is taken up by chemical synthesizing machines, which will produce the gasses necessary to start forming a breathable atmosphere on the planet.'
	color=TextColors.r2

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

class R3(Room):
	name='Food Stores'
	info='The room is filled floor to ceiling with hydroponic gardens growing, potatoes, carrots, tomatoes, wheat, beans, and what appears to be almost every other fruit, vegetable, and grain. Below the glass floor, large freezers were being filled by robotic haversters which must have been running most of the flight.'
	color=TextColors.r3

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

class R4(Room):
	name='Reactor'
	info='One of the most impressive feats of human engineering at the time, the reactor was built to use incredibly strong magnetic fields to stabilize a small solar core, then harvest the energy of the miniature sun using an encompassing array of solar panels.'
	color=TextColors.r4

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

class R5(Room):
	name='Mainframe'
	info='The sheer scale of the computer was enough to make most stop in their tracks and gaze in awe. This was the heart of the ship\'s computer, GALILEO. Designed to handle flight operations and maintenance during the 422 year journey, plus the terraforming and preparation of Proxima Centauri b, GALILEO was the most advanced AI ever built by humans.'
	color=TextColors.r5

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

class R6(Room):
	name='Escape Pod'
	info='A small escape pod located in a hanger bay. With the ability to take off and land, it was more of an exploration vehicle than an escape pod. The interior contains little more than an area to store necessary supplies, a cryopod in case the ship is stranded, and a transmitter to allow rescuers to locate the ship.'
	color=TextColors.r6

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

class R7(Room):
	name='Engine'
	info='Although this engine could push the ship up to speeds of 1/5 the speed of light, given the close proximity to the Alpha Centauri system, it would take slightly longer to reach the planet due to the long acceleration and deceleration needed.'
	color=TextColors.r7

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

class R8(Room):
	name='Shield Generator'
	info='The size of a city block, the device converts energy to form small electric, magnetic, and gravitational fields around the ship. The shield generator provides a moderate amount of protection against strong solar winds, asteriods and other debris, and potentially any alien ships if such an encounter were to occur.'
	color=TextColors.r8

	def __init__(self, new=True):
		super().__init__(
			new=new
		)

rooms = [R0(), R1(), R2(), R3(), R4(), R5(), R6(), R7(), R8()]
for ri in fix_rooms:
	rooms[ri].fix_done = False
for ri in quick_rooms:
	rooms[ri].quick_done = False

## MARK: Convenience logs ##
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
	log(Text('--Map-- ', end=False), save=False, clear=True, validate=False)
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
			room_block = TextBlock(texts=[Text(rooms[p_room].name, styles=[TextStyles.bold]), Text(rooms[p_room].info), spacer()])
			if p_room in fix_rooms:
				room_block.add_text(Text(rooms[p_room].fix_info, fg=TextColors.danger)) 
				room_block.add_text(spacer())
			room_block.write_log()
		elif moved:
			TextBlock(texts=[Text(rooms[p_room].name, styles=[TextStyles.bold]), spacer()]).write_log()
		else:
			TextBlock(texts=[Text('There is no door that way'), spacer()]).write_log()

def run_cmd(cmd):
	if cmd == '?':
		print_help()
	elif cmd == 'log':
		print_logs()
	elif cmd == 'map':
		print_map()
	elif cmd == 'look':
		look_block = TextBlock(texts=[Text(rooms[p_room].info), spacer()])
		if p_room in fix_rooms:
			if not rooms[p_room].fix_done:
				look_block.add_text(Text(rooms[p_room].fix_info, fg=TextColors.danger))
				look_block.add_text(spacer())
		look_block.write_log()
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
	elif cmd == 'inventory':
		inventory_block = TextBlock()
		inventory_block.add_text(Text('Inventory items'))
		for item in inventory:
			inventory_block.add_text(Text(item.name, end=False))
			inventory_block.add_text(Text(' - {0}'.format(item.info), styles=[TextStyles.faint]))
		inventory_block.add_text(spacer())
		inventory_block.write_log()
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
		exit()

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
