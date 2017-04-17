import random
import boto3

from flask import Flask
from flask import jsonify
app = Flask(__name__)

valid_max_players = [ 2, 4 ]
valid_modes = [ 'ffa' ]

gamelift = boto3.client('gamelift')
gamelift_fleet = 'fleet-123' # insert actual fleet

def generate_player_id():
	return str(random.randint(0, 10000000))

@app.route('/search/<game_type>', methods=['GET'])
def search(game_type):
	# parse game type
	game_max_players = int(game_type.split(',')[0])
	game_mode = game_type.split(',')[1]
	print('game type parsed as {0} player {1} game'.format(game_max_players, game_mode))
	
	# check game type is valid
	if not game_max_players in valid_max_players or not game_mode in valid_modes:
		return jsonify({ 'msg': 'error', 'error': 'invalid max players or game mode' }), 404
	
	# start search for game sessions
	print('sending initial search')
	response = gamelift.search_game_sessions(\
		FleetId = gamelift_fleet,\
		FilterExpression = 'maximumSessions={0} AND gameSessionName={1} AND hasAvailablePlayerSessions=true'.format(game_max_players, game_mode),\
		SortExpression = "creationTimeMillis ASC")
	
	# check for search failure
	if not response:
		return jsonify({ 'msg': 'error', 'error': 'failed to search gamelift for game session' }), 500
	
	print('initial search successful')
	
	# loop through search results
	while True:
		# loop through page of game sessions
		for session in response['GameSessions']:
			# check session is good
			if session['CurrentPlayerSessionCount'] < session['MaximumPlayerSessionCount'] and\
				session['Status'] == 'ACTIVE' and\
				session['PlayerSessionCreationPolicy'] == 'ACCEPT_ALL':
					# try to reserve spot in session
					response2 = gamelift.create_player_session(\
						GameSessionId = session['GameSessionId'],\
						PlayerId = generate_player_id())
					
					# return reserved session if successful
					if response2:
						return jsonify( {\
							'msg': 'success',\
							'id': response2['PlayerSession']['PlayerSessionId'],\
							'ip': response2['PlayerSession']['IpAddress'],\
							'port': response2['PlayerSession']['Port'] } )
		
		# check if at end of search results
		if not response['NextToken']:
			break
		else:
			# get next page of search results
			response = gamelift.search_game_sessions(\
				FleetId = gamelift_fleet,\
				FilterExpression = 'maximumSessions={0} AND gameSessionName={1} AND hasAvailablePlayerSessions=true'.format(game_max_players, game_mode),\
				SortExpression = "creationTimeMillis ASC",\
				NextToken = response['NextToken'])
	
	# search yielded no game sessions, so create a new game session
	response = gamelift.create_game_session(\
		FleetId = gamelift_fleet,\
		MaximumPlayerSessionCount = game_max_players,\
		Name = game_mode)
	
	# check for session creation failure
	if not response:
		return jsonify({ 'msg': 'error', 'error': 'failed to create gamelift game session' }), 500
	
	# try to reserve spot in created session
	response2 = gamelift.create_player_session(\
		GameSessionId = response['GameSession']['GameSessionId'],\
		PlayerId = generate_player_id())
	
	# return reserved session if successful
	if response2:
		return jsonify( {\
			'msg': 'success',\
			'id': response2['PlayerSession']['PlayerSessionId'],\
			'ip': response2['PlayerSession']['IpAddress'],\
			'port': response2['PlayerSession']['Port'] } )
	
	return jsonify({ 'msg': 'error', 'error': 'failed to join created session' }), 500

if __name__ == '__main__':
	app.run('0.0.0.0', 8080, True)