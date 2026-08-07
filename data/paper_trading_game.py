from data.firebase_controller import create_game, update_game, get_all_games, get_game_detail, get_paper_trader # get_game, get_owner, update_game, delete_game

# Create a multiplayer game where players can trade stocks and compete for the highest portfolio value using the PaperTrader module
class PaperTraderGame:
    def __init__(self, name, starting_amount, owner, players=[], has_options=False, has_fee=False):
        self.name = name
        self.starting_amount = starting_amount
        self.owner = owner
        self.players = players
        self.has_options = has_options
        self.has_fee = has_fee

    def create_game(self):
        print("Creating game...")
        create_game(self.to_dict())

    def update_game(self):
        print("Updating game...")
        update_game(self.to_dict())

    @staticmethod
    def get_games(user):
        return get_all_games(user)
    
    @staticmethod
    def get_paper_trader(game, user):
        return get_paper_trader(game, user)

    @staticmethod
    def get_game_detail(game, user):
        return get_game_detail(game, user)

    def to_dict(self):
        return {
            'players': self.players,
            'name': self.name,
            'starting_amount': self.starting_amount,
            'owner': self.owner,
            'has_options': self.has_options,
            'has_fee': self.has_fee
        }
    
