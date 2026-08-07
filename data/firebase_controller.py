from data.firebase_init import get_db, get_auth, get_fbauth
from data.paper_trader import PaperTrader


db = get_db()
auth = get_auth()
fbauth = get_fbauth()

def create_user(email, password):
    if password is not None:
        uid = auth.create_user_with_email_and_password(email, password)
    else:
        uid = fbauth.create_user(
            email=email,
            email_verified=True,
            disabled=False
        )
        uid = {'idToken': uid.uid, 'registered': True}
    from data.user import User
    user = User(uid['idToken'], email)
    # Add a new doc in collection 'cities' with ID 'LA'
    db.collection(u'users').document(email).set(user.to_dict())
    print(f'Sucessfully created new user.')

def get_user(email, password):
    if password is not None: # Regular login
        user = auth.sign_in_with_email_and_password(email, password)
    else: # Google OAuth login
        user = fbauth.get_user_by_email(email)
        user = {'idToken': user.uid, 'registered': True}
    uid = user['idToken']
    print(f'Successfully fetched user data: {uid}')
    print(user)
    if not user['registered']:
        print(f'Email not verified. Sending verification email.')
        auth.send_email_verification(uid)
    # Get user data from database
    user_data = db.collection(u'users').document(email).get().to_dict()
    print('user_data: ', user_data)
    return user, user_data

def reset_password(email):
    auth.send_password_reset_email(email)
    print(f'Successfully sent password reset email.')

def create_game(game):
    print(game)
    # Check that all players exist
    game['players'] = list(set(game['players']))
    print()
    for player in game['players']:
        if not db.collection(u'users').document(player).get().exists:
            raise Exception(f'Player {player} does not exist.')

    # Check that game name does not already exist
    if db.collection(u'games').document(game['name']).get().exists:
        raise Exception(f'Game {game["name"]} already exists.')
    
    db.collection(u'games').document(game['name']).set(game)
    print(f'Successfully created new game: {game}')

    # Make portfolio for each player
    for player in game['players']:
        new_trader = PaperTrader(game['name'], [], game['starting_amount'], game['starting_amount'], player, game['has_options'], game['has_fee'])
        db.collection(u'games').document(game['name']).collection(u'portfolios').document(player).set(new_trader.to_dict())
        print(f'Successfully created new portfolio for {player}')

        # Add game to user's list of games
        user_data = db.collection(u'users').document(player).get().to_dict()
        user_data['games'].append(game['name'])
        db.collection(u'users').document(player).set(user_data)

def update_game(game):
    print(game)
    # Check that all players exist
    for player in game['players']:
        if not db.collection(u'users').document(player).get().exists:
            raise Exception(f'Player {player} does not exist.')
    
    # Get old players and new players.
    all_players = db.collection(u'games').document(game['name']).get().to_dict()['players'] + game['players']
    all_players = list(set(all_players))
    game['players'] = all_players    
    db.collection(u'games').document(game['name']).set(game)
    print(f'Successfully updated game: {game}')

    # Make portfolio for each player.
    # If player already has portfolio, update it.
    for player in game['players']:
        if db.collection(u'games').document(game['name']).collection(u'portfolios').document(player).get().exists:
            print(f'Updating portfolio for {player}')
            updatePortfolio(game['name'], PaperTrader(game['name'], [], game['starting_amount'], game['starting_amount'], player, game['has_options'], game['has_fee']), update_game=True)
        else:
            print(f'Creating portfolio for {player}')
            new_trader = PaperTrader(game['name'], [], game['starting_amount'], game['starting_amount'], player, game['has_options'], game['has_fee'])
            db.collection(u'games').document(game['name']).collection(u'portfolios').document(player).set(new_trader.to_dict())
            print(f'Successfully created new portfolio for {player}')

            # Add game to user's list of games
            user_data = db.collection(u'users').document(player).get().to_dict()
            user_data['games'].append(game['name'])
            db.collection(u'users').document(player).set(user_data)

def get_all_games(user):
    all_games = []
    user_data = db.collection(u'users').document(user).get().to_dict()
    for game in user_data['games']:
        # Get games from database
        game_data = db.collection(u'games').document(game).collection(u'portfolios').document(user).get().to_dict()
        all_games.append(PaperTrader(game_data['name'], game_data['portfolio'], game_data['initial'], game_data['capital'], game_data['id'], game_data['has_options'], game_data['has_fee']))
    return all_games

def get_paper_trader(game, user):
    data = db.collection(u'games').document(game).collection(u'portfolios').document(user).get().to_dict()
    return PaperTrader(data['name'], data['portfolio'], data['initial'], data['capital'], data['id'], data['has_options'], data['has_fee'])

def get_game_detail(game, user):
    # Note: Use of CollectionRef stream() is prefered to get()
    docs = db.collection(u'games').document(game).collection(u'portfolios').stream()
    main_user = None
    other_users = []
    for doc in docs:
        d = doc.to_dict()
        print('Check', d['id'], user)
        if d['id'] == user:
            main_user = PaperTrader(d['name'], d['portfolio'], d['initial'], d['capital'], d['id'], d['has_options'], d['has_fee'])
        else:
            print(d)
            other_users.append(PaperTrader(d['name'], d['portfolio'], d['initial'], d['capital'], d['id'], d['has_options'], d['has_fee']))
    return main_user, other_users

def updatePortfolio(game, paper_trader, update_game=False):
    # Update game
    if update_game:
        # Update only the has_options and has_fee fields
        current = db.collection(u'games').document(game).collection(u'portfolios').document(paper_trader.id).get().to_dict()
        current['has_options'] = paper_trader.has_options
        current['has_fee'] = paper_trader.has_fee
        db.collection(u'games').document(game).collection(u'portfolios').document(paper_trader.id).set(current)
    else:
        db.collection(u'games').document(game).collection(u'portfolios').document(paper_trader.id).set(paper_trader.to_dict())

if __name__ == '__main__':
    # add_data()
    # get_data()

    get_user('saptak.das625@gmail.com', 'password')
    