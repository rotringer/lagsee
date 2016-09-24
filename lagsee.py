#
# Lagsee 
# 7z backup script
#
# Author: R&S Laboratories
#


import os
import sys
import json
import hashlib
import binascii
from datetime import datetime
import fnmatch
import subprocess
import getpass
import signal


aborted = False

def main():
	if len(sys.argv) < 2:
		printUsage()
		sys.exit()

	signal.signal(signal.SIGINT, signalHandler)

	commands = {
		'help': commandHelp,
		'version': printVersion,
		'backup': commandBackup,
		'check': commandCheck,
		'restore': commandRestore,
		'verify': commandVerify
	}

	command = sys.argv[1]

	if command in commands:
		commands[command]()
	else:
		print('Command not found')

	sys.exit()


def signalHandler(signum, frame):
	global aborted
	aborted = True


def loadConfig(path):
	print('Loading config: ' + path)
	with open(path) as config_file:    
	    return json.load(config_file)


def initializeKey(config):
	if 'password' in config:
		enckey = getEncKey(config['password'])
		print('Warning: config file contains password. Use enckey:')
		print('  ' + enckey)
		config['enckey'] = enckey
	else:
		password = getpass.getpass()
		config['password'] = password
		enckey = getEncKey(password)
		if config['enckey'] != enckey:
			print('Error: Password mismatch')
			sys.exit()

	config['salt'] = getSalt(config['password'])


def printVersion():
	print('Lagsee version 0.0.1')

def printUsage():
	printVersion()
	print('Usage: lagsee.py command [config.json] [params]')

def commandHelp():
	print('Not implemented')

def commandBackup():
	printVersion()
	if len(sys.argv) < 3:
		print('Error: no config file spcified')
		sys.exit()

	config = loadConfig(sys.argv[2])
	initializeKey(config)

	if not ('directories' in config):
		print('Error: no backup directories specified')
		sys.exit()

	log = None
	if 'log_dir' in config:
		logfilename = datetime.now().strftime('%Y%m%d%H%M%S') + '.log'
		logfilepath = config['log_dir']+'/'+logfilename
		log = open(logfilepath, 'w')

	writeLog(log, 'Backup started', True)

	status = {'ignored':0, 'skipped':0, 'updated':0}

	ret = True

	for dirs in config['directories']:
		dir_src = os.path.abspath(dirs['source'])
		dir_dst = os.path.abspath(dirs['destination'])

		os.chdir(dir_src)
		writeLog(log, 'Backup directory: ' + dir_src + '\n  -> ' + dir_dst, True)
		
		filelist = []
		ret = backupDirectory(log, filelist, config, status, False, dir_src, dir_dst)

		if not ret:
			break;

		if status['updated'] > 0:
			writeFileList(log, filelist, dir_dst)


	summary = '  Updated: ' + str(status['updated']) + \
			  ', Skipped: ' + str(status['skipped']) + \
			  ', Ignored: ' + str(status['ignored'])

	print('\n')

	if ret:
		writeLog(log, 'Backup finished\n' + summary, True)
	else:
		writeLog(log, 'Backup aborted!\n' + summary, True )

	print('\n')

	if log is not None:
		log.close()


def commandCheck():
	printVersion()
	if len(sys.argv) < 3:
		print('Error: no config file spcified')
		sys.exit()

	config = loadConfig(sys.argv[2])
	initializeKey(config)

	if not ('directories' in config):
		print('Error: no backup directories specified')
		sys.exit()

	status = {'ignored':0, 'skipped':0, 'updated':0}

	ret = True

	for dirs in config['directories']:
		dir_src = os.path.abspath(dirs['source'])
		dir_dst = os.path.abspath(dirs['destination'])

		os.chdir(dir_src)
		print('Check directory: ' + dir_src + '\n  -> ' + dir_dst, True)

		filelist = []
		ret = backupDirectory(None, filelist, config, status, True, dir_src, dir_dst)
		
		if not ret:
			break;

	summary = '  Updated: ' + str(status['updated']) + \
		      ', Skipped: ' + str(status['skipped']) + \
		      ', Ignored: ' + str(status['ignored'])

	print('\n')

	if ret:
		print('Check finished\n' + summary)
	else:
		print('Check aborted!\n' + summary)

	print('\n')


def commandRestore():
	print('Not implemented')

def commandVerify():
	print('Not implemented')







def getEncKey(password):
	return binascii.hexlify(hashlib.pbkdf2_hmac('sha256', password.encode(), b'enckey', 100000)).decode()

def getSalt(password):
	return binascii.hexlify(hashlib.pbkdf2_hmac('sha256', password.encode(), b'salt', 100000, 8)).decode()

def getPathHash(salt, path):
	text = salt + ":" + path + ":" + getPathMTime(path) + ":" + str(os.path.getsize(path))
	return hashlib.sha1(text.encode()).hexdigest()

def getPathMTime(path):
	return datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y%m%d%H%M%S')


def matchPatterns(filename, patterns):
	for pat in patterns:
		if fnmatch.fnmatch(filename, pat):
			return True
	return False


def writeLog(log, text, withPrint=False):
	if log is not None:
		log.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S] ') + text + '\n')
	if withPrint:
		print(text)


def pack7z(log, srcfile, dstfile, password, volume=0, nocompress=False, compresslevel=-1):
	params = [
		'7z',
		'a',
		'-p' + password,
		'-mhe=on'
	]

	if volume != 0:
		params.append('-v' + str(volume) + 'm')

	if nocompress:
		params.append('-mx=0')
	else:
		if compresslevel >= 0:
			params.append('-mx=' + str(compresslevel))

	params.append(dstfile)
	params.append(srcfile)

	proc = subprocess.Popen(
		params,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE)

	out, err = proc.communicate()
	ret = proc.returncode

	writeLog(log, out.decode())

	return ret


def backupDirectory(log, filelist, config, status, checkmode, path_src, path_dst, path_base=''):
	dir_path = path_src + '/' + path_base

	sys.stdout.write("\r")
	writeLog(log, 'checking: ' + dir_path, True)

	files = os.listdir(dir_path)
	for file in files:

		if aborted:
			return False

		if not checkmode:
			sys.stdout.write("\r Updated: %d, Skipped: %d, Ignored: %d" % (status['updated'], status['skipped'], status['ignored']) )

		rpath = path_base + file
		#fpath = path_src + '/' + rpath

		ignore = False
		if 'ignores' in config:
			ignore = matchPatterns(file, config['ignores'])

		if ignore:
			if not checkmode:
				writeLog(log, 'ignored: ' + rpath)
			status['ignored'] = status['ignored'] + 1
		else:
			if os.path.isdir(rpath):
				ret = backupDirectory(log, filelist, config, status, checkmode, path_src, path_dst, rpath+'/')
				if not ret:
					return False

			else:
				pathhash = getPathHash(config['salt'], rpath)
				efilename = pathhash + '.7z'
				efilepath = path_dst + '/' + efilename

				filelist.append(pathhash)

				if os.path.exists(efilepath) or os.path.exists(efilepath+'.001'):
					if not checkmode:
						writeLog(log, 'skipped: ' + rpath)
					status['skipped'] = status['skipped'] + 1
				else:
					nocompress = False
					if 'nocompress' in config:
						nocompress = matchPatterns(file, config['nocompress'])
					
					volume = 0
					if 'volume' in config:
						volume = config['volume']
					
					compresslevel = -1
					if 'compresslevel' in config:
						compresslevel = config['compresslevel']

					filesize = os.path.getsize(rpath)
					if filesize/1024/1024 < volume:
						volume = 0

					if not checkmode:
						writeLog(log, 'packing: ' + rpath + '\n  -> ' + efilename)
						ret = pack7z(log, rpath, efilepath, config['password'], volume, nocompress, compresslevel)

						if ret != 0 or aborted:
							if ret != 0:
								print('\n')
								writeLog(log, 'failed: ' + rpath + '\n  -> ' + efilename, True)

							try:
								os.remove(efilepath)
								writeLog(log, 'removed: ' + efilename)
							except OSError:
								pass

							return False

					status['updated'] = status['updated'] + 1

	return True

def writeFileList(log, filelist, path_dst):
	filename = 'filelist_' + datetime.now().strftime('%Y%m%d%H%M%S') + '.txt'
	with open(path_dst + '/' + filename, 'w') as f:
		for file in filelist:
			f.write(file + '\n')
	writeLog(log, 'Write filelist: ' + filename)


main()

