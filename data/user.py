from data.firebase_init import db
from data.firebase_controller import create_user, get_user, reset_password

class User:
    """
    User Data Model. Stores ChatGPT conversation information for each user.
    """

    def __init__(self, user_id, email, user_data={}, conversations=[], favorite_stocks=[], games=[]):
        """
        Initializes a new User object.
        
        :param user_id: User ID
        """
        self.user_id = user_id
        self.email = email
        self.user_data = user_data
        self.conversations = conversations
        self.favorite_stocks = favorite_stocks
        self.games = games

    def add_conversation(self, conversation):
        self.conversations.append(conversation)
        self.save()

    def update_conversation(self, conversation):
        for i in range(len(self.conversations)):
            if self.conversations[i]['cid'] == conversation['cid']:
                self.conversations[i] = conversation
                self.save()
                break

    def get_conversations(self):
        return self.conversations
    
    def remove_conversation(self, conversation):
        self.conversations.remove(conversation)
        self.save()

    def add_game(self, game):
        self.games.append(game)
        self.save()
    
    def get_games(self):
        return self.games
    
    def add_favorite_stock(self, stock):
        self.favorite_stocks.append(stock.upper())
        self.save()

    def get_favorite_stocks(self):
        return self.favorite_stocks
    
    def remove_favorite_stock(self, stock):
        self.favorite_stocks.remove(stock)
        self.save()

    @staticmethod
    def create_user(email, password=None):
        """
        Creates a new user in the database.
        
        :param email: Email of the user
        :param password: Password of the user
        :return: User object
        """
        create_user(email, password)

    
    @staticmethod
    def get_user(email, password=None):
        """
        Login a user and create User Object.
        
        :param email: Email of the user
        :return: User object
        """
        user, user_data = get_user(email, password)
        print(user_data)
        return User(user['idToken'], email, user_data=user, conversations=user_data['conversations'], favorite_stocks=user_data['favorite_stocks'], games=user_data['games'])
    
    @staticmethod
    def reset_password(email):
        """
        Reset password of a user.
        
        :param email: Email of the user
        :return: User object
        """
        reset_password(email)

    @staticmethod
    def get_user_by_email(email):
        """
        Get a user by email.
        
        :param email: Email of the user
        :return: User object
        """
        user_data = db.collection(u'users').document(email).get().to_dict()
        return User(user_data['user_id'], email, user_data=user_data, conversations=user_data['conversations'], favorite_stocks=user_data['favorite_stocks'], games=user_data['games'])
    
    def save(self):
        """
        Saves the user object to the database.
        
        :return: None
        """
        db.collection(u'users').document(self.email).set(self.to_dict())

    def to_dict(self):
        """
        Converts User object to a dictionary.
        
        :return: Dictionary of User object
        """
        return {
            'user_id': self.user_id,
            'email': self.email,
            'conversations': self.conversations,
            'favorite_stocks': self.favorite_stocks,
            'games': self.games
        }