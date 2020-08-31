import time
import sys
import shutil
import tty
import termios

## MARK: Constants ##
LOG_COLS, LOG_ROWS = shutil.get_terminal_size()
CPU = 'GALILEO'
CMDS = {'?': 'Print the help page', 'log': 'Read the on-suit log book', 'map': 'View the ship maps', 'look': 'Look around the room', 'examine': 'Interact with an object in the room', 'use': 'Use an object from the inventory', 'up': 'Move up one room', 'down': 'Move down one room', 'left': 'Move left one room', 'right': 'Move right one room', 'save': 'Save the game', 'quit': 'Quit the game'}
SHIP = [
	[None, 0, None],
	[1, 2, 3],
	[4, 5, 6],
	[7, None, 8]
]

## MARK: Global variables ##
logs = []
name = ''
oxy = 10
eng = 10
player_room = 0
doors_locked = True
inventory = []

## MARK: Convenience functions ##
wait = lambda s: time.sleep(s)

def getch():
	fd = sys.stdin.fileno()
	old_settings = termios.tcgetattr(fd)
	try:
		tty.setraw(sys.stdin.fileno())
		ch = sys.stdin.read(1)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	return ch

## MARK: Printing to console ##
def clear_log():
	print('\x1b[H\x1b[J', end='')
	sys.stdout.flush()

def log(text, slow=False, styles=None, fg=None, bg=None, delay=0.05, center=False, save=True, clear=False, row=None, end=True, log=False):
	global logs
	if log:
		save = False
		end = False
	LOG_STYLE = {'bold': 1, 'faint': 2, 'italic': 3, 'underline': 4, 'blink': 5, 'first_blink': 6, 'reverse': 7, 'hide': 8, 'strike': 9}
	LOG_COLOR = {'title': 14, 'cpu_name': 10, 'cpu': 11, 'player_name': 12, 'player_head': 7, 'danger': 9, 'oxy': 69, 'eng': 46}
	forced = True
	if save and not clear and logs and sum([1 if c == '\n' else 0 for c in logs[-1]]) > LOG_ROWS - 5:
		clear = True
		forced = False
		row = 3
		print('\x1b[2H\x1b[J', end='')
	sys.stdout.flush()
	clear_log() if clear and forced else None
	mods = '\x1b[{0}H'.format(row) if row else ''
	mods += ''.join(['\x1b[{0}m'.format(LOG_STYLE[style]) for style in styles]) if styles else ''
	mods += '\x1b[38;5;{0}m'.format(LOG_COLOR[fg]) if fg else ''
	mods += '\x1b[48;5;{0}m'.format(LOG_COLOR[bg]) if bg else ''
	mods += '\x1b[{0};{1}H'.format(row, LOG_COLS // 2 + 1 - len(text) // 2) if center else ''
	print(mods, end='')
	if len(text) > LOG_COLS and not log:
		end_space = text.rindex(' ', 0, LOG_COLS)
		text = text[:end_space] + '\n' + text[end_space + 1:]
	if slow:
		for c in text:
			sys.stdout.write(c)
			sys.stdout.flush()
			wait(delay)
	else:
		print(text, end='')
	print('\x1b[m', end='\n' if end else '')
	sys.stdout.flush()
	if save:
		if clear:
			logs.append(mods + text + '\x1b[m' + ('\n' if end else ''))
		else:
			logs[-1] += mods + text + '\x1b[m' + ('\n' if end else '')

spacer = lambda n=1: log('\n' * (n - 1))

def prompt(allowed=[], blocked=[], lower=True):
	global logs
	log('\x1b7> ', end=False)
	text = input()
	if lower:
		text = text.lower()
	while (allowed and text.strip() not in allowed) or (blocked and text.strip() in blocked) or len(text) > LOG_COLS - 3:
		log('\x1b8\x1b[J> ', end=False)
		text = input()
		if lower:
			text = text.lower()
	logs[-1] += '{0}\n'.format(text.strip())
	return text.strip()

## MARK: Object interactions ##
def examine_console():
	global doors_locked
	log('What would you like to do?')
	log('a) Read mission history')
	log('b) Unlock doors')
	log('c) Close')
	option = prompt(allowed=['a', 'b', 'c'])
	if option == 'a':
		log('[[INSERT MISSION HISTORY]]')
	elif option == 'b':
		if doors_locked:
			doors_locked = False
			log('Doors unlocked')
			log('<You can now move through the ship>', styles=['faint'], save=False)
		else:
			log('Doors already unlocked')

def examine_door():
	log('The door appears to be locked' if doors_locked else 'The door is unlocked')

## MARK: Room data ##
rooms = [
	{
		'name': 'Bridge',
		'info': 'The room has a single chair and a console at the front. To the left is an open cryopod. To the right is storage box. Behind is a door.',
		'objects': {
			'console': examine_console,
			'box': {},
			'door': examine_door
		},
		'new': False,
		'color': 21
	},
	{
		'name': 'Oxygen Tanks',
		'info': '',
		'objects': {},
		'new': True,
		'color': 69
	},
	{
		'name': 'Terraforming Equipment',
		'info': '',
		'objects': {},
		'new': True,
		'color': 240
	},
	{
		'name': 'Food Stores',
		'info': '',
		'objects': {},
		'new': True,
		'color': 208
	},
	{
		'name': 'Reactor',
		'info': '',
		'objects': {},
		'new': True,
		'color': 76
	},
	{
		'name': 'Mainframe',
		'info': '',
		'objects': {},
		'new': True,
		'color': 248
	},
	{
		'name': 'Escape Pod',
		'info': '',
		'objects': {},
		'new': True,
		'color': 200
	},
	{
		'name': 'Left Engine',
		'info': '',
		'objects': {},
		'new': True,
		'color': 92
	},
	{
		'name': 'Right Engine',
		'info': '',
		'objects': {},
		'new': True,
		'color': 80
	}
]

## MARK: Tools ##
def next():
	log('<Press any key to continue>', styles=['faint'], save=False, end=False)
	getch()

def print_meters():
	log('\x1b7\x1b[H', save=False, end=False)
	log('O2: [', save=False, end=False)
	log('=' * oxy, fg='oxy', save=False, end=False)
	log('] {0}/10 | \u26A1: ['.format(oxy), save=False, end=False)
	log('=' * eng, fg='eng', save=False, end=False)
	log('] {0}/10 | Help (?)'.format(eng), save=False)
	log('\x1b8', save=False, end=False)

def to_game(show_meters=True):
	log(logs[-1], clear=True, end=False, log=True)
	print_meters() if show_meters else None

def print_logs():
	i = len(logs) - 1
	while True:
		log('Entry [{0}/{1}] | Previous (a) | Next (d) | Quit (q)'.format(str(i + 1).rjust(len(str(len(logs)))), len(logs)), save=False, clear=True)
		log(logs[i], log=True)
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
	log('--Map-- \x1b[2m(press any key to exit)', save=False, clear=True)
	for i, row in enumerate(SHIP):
		l1 = '\x1b[{0};{1}H'.format((i + 1) * 3, LOG_COLS // 2 - 3)
		l2 = '\x1b[{0};{1}H'.format((i + 1) * 3 + 1, LOG_COLS // 2 - 3)
		l3 = '\x1b[{0};{1}H'.format((i + 1) * 3 + 2, LOG_COLS // 2 - 3)
		for n, room in enumerate(row):
			if room is None:
				l1 += '   '
				l2 += '   '
				l3 += '   '
			else:
				log('\x1b[38;5;{0}m{1}'.format(rooms[room]['color'], rooms[room]['name']), save=False, row=3 + room, end=False)
				l1 += '\x1b[48;5;{0}m---\x1b[m'.format(rooms[room]['color'])
				l2 += '\x1b[48;5;{0}m|{1}|\x1b[m'.format(rooms[room]['color'], '\x1b[5m\x1b[38;5;9m*\x1b[m\x1b[48;5;{0}m'.format(rooms[room]['color']) if room == player_room else ' ')
				l3 += '\x1b[48;5;{0}m---\x1b[m'.format(rooms[room]['color'])
		log(l1, save=False, end=False)
		log(l2, save=False, end=False)
		log(l3, save=False, end=False)
	getch()
	to_game()


def print_help():
	log('--List of commands-- \x1b[2m(press any key to exit)', save=False, clear=True)
	[log('{0} \x1b[2m- {1}'.format(cmd, cmd_info), save=False) for cmd, cmd_info in CMDS.items()]
	getch()
	to_game()

## MARK: Logic ##
def move(direction):
	global player_room
	log(str(player_room))
	if direction == 'down' and doors_locked:
		log('The door appears to be locked')
		spacer()
	else:
		player_loc = ()
		moved = True
		for i in range(len(SHIP)):
			for n in range(len(SHIP[0])):
				if SHIP[i][n] == player_room:
					player_loc = (i, n)
		if direction == 'up' and player_loc[0] != 0 and SHIP[player_loc[0] - 1][player_loc[1]]:
			player_room = SHIP[player_loc[0] - 1][player_loc[1]]
		elif direction == 'down' and player_loc[0] != len(SHIP) - 1 and SHIP[player_loc[0] + 1][player_loc[1]]:
			player_room = SHIP[player_loc[0] + 1][player_loc[1]]
		elif direction == 'left' and player_loc[1] != 0 and SHIP[player_loc[0]][player_loc[1] - 1]:
			player_room = SHIP[player_loc[0]][player_loc[1] - 1]
		elif direction == 'right' and player_loc[1] != len(SHIP[0]) - 1 and SHIP[player_loc[0]][player_loc[1] + 1]:
			player_room = SHIP[player_loc[0]][player_loc[1] + 1]
		else:
			moved = False
		if moved and rooms[player_room]['new']:
			rooms[player_room]['new'] = False
			log(rooms[player_room]['info'])
			spacer()
		elif not moved:
			log('There is no door that way')
			spacer()


def run_cmd(cmd):
	if cmd == '?':
		print_help()
	elif cmd == 'log':
		print_logs()
	elif cmd == 'map':
		print_map()
	elif cmd == 'look':
		log(rooms[player_room]['info'])
		spacer()
	elif cmd == 'examine':
		spacer()
		log('What would you like to examine?')
		for obj in rooms[player_room]['objects'].keys():
			log(obj)
		log('nothing')
		option = prompt(allowed=list(rooms[player_room]['objects'].keys()) + ['nothing'])
		if option != 'nothing':
			rooms[player_room]['objects'][option]()
		spacer()
	elif cmd == 'use':
		pass
	elif cmd in ['up', 'down', 'left', 'right']:
		move(cmd)
	elif cmd == 'save':
		pass
	elif cmd == 'quit':
		pass

## MARK: Intro ##
def scan_cutscene():
	clear_log()
	wait(1)
	for i in range(3, LOG_ROWS - 1):
		log('-' * LOG_COLS, fg='danger', save=False, row=i, end=False)
		wait(0.1)
		clear_log()
	for i in range(LOG_ROWS - 1, 3, -1):
		log('-' * LOG_COLS, fg='danger', save=False, row=i, end=False)
		wait(0.1)
		clear_log()
	to_game(show_meters=False)

def title_screen():
	clear_log()
	wait(3)
	log('CENTAURI', styles=['bold', 'underline'], slow=True, fg='title', delay=0.2, center=True, save=False, row=5)
	log('Press any key to start', styles=['blink', 'bold'], center=True, save=False, row=15)
	getch()

def start_cutscene():
	global name
	clear_log()
	wait(3)
	log('W A R N I N G', styles=['blink', 'bold'], fg='danger', center=True, clear=True, row=3)
	wait(3)
	log('[???]', fg='cpu_name', row=6)
	log('Hull Breach. Immediate action required.', slow=True, styles=['bold'], fg='danger')
	spacer()
	wait(1)
	log('Prematurely lifting cryosleep protocol', slow=True, fg='cpu', end=False)
	wait(1)
	log('...', slow=True, fg='cpu', delay=1)
	wait(1)
	log('Opening cryopod', slow=True, fg='cpu', end=False)
	log('...', slow=True, fg='cpu', delay=1)
	spacer()
	wait(1)
	log('Good morning, captain. Sorry for the early wake up, but there appears to be an issue with the ship.', slow=True, fg='cpu')
	spacer()
	wait(1)
	log('[???]', fg='player_name')
	log('Ugh. Wh~ what? My head is spinning...', fg='player_head')
	next()
	log('[{0}]'.format(CPU), fg='cpu_name', clear=True, row=3)
	log('Your memory may be a bit foggy since I had to temporarily abort the cryosleep. I am the ship\'s computer, GALILEO.', slow=True, fg='cpu')
	spacer()
	wait(1)
	log('[???]', fg='player_name')
	log('Hmm... I think that sounds familiar... What was my name again?', fg='player_head')
	name = prompt(blocked=[''], lower=False)
	spacer()
	wait(1)
	log('[{0}]'.format(name), fg='player_name')
	log('Yes! My name is {0}.'.format(name), fg='player_head')
	spacer()
	wait(1)
	log('[{0}]'.format(CPU), fg='cpu_name')
	log('You seem to have more trouble remembering than was expected. This is worrying.', slow=True, fg='cpu')
	spacer()
	wait(1)
	log('Running health scan', slow=True, fg='cpu', end=False)
	log('...', slow=True, fg='cpu', delay=1)
	spacer()
	scan_cutscene()
	log('Luckily you appear to physically ok.', slow=True, fg='cpu')
	spacer()
	wait(1)
	log('I recommend exploring the ship to refamiliarize yourself with the mission.', slow=True, fg='cpu')
	next()
	log('[{0}]'.format(CPU), fg='cpu_name', clear=True, row=3)
	print_meters()
	log('You might want to press the help button on your suit to see what actions you can perform.', slow=True, fg='cpu')
	log('<Press \'?\' to see the list of actions>', styles=['faint'], save=False)
	cmd = prompt(allowed=['?'])
	run_cmd(cmd)

## MARK: Game start ##
def game_start():
	while True:
		cmd = prompt(allowed=CMDS.keys())
		run_cmd(cmd)

def init():
	title_screen()
	start_cutscene()
	game_start()

init()
