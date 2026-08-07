import pyrebase
from firebase_admin import credentials, auth as fbauth, firestore, initialize_app
from data.firebase_config import firebaseConfig

# Initialize Firestore DB
cred = credentials.Certificate('investify-d81b6-firebase-adminsdk-nwh3q-7728897492.json')
default_app = initialize_app(cred)
db = firestore.client()

pb = pyrebase.initialize_app(firebaseConfig)

auth = pb.auth()

def get_pb():
    return pb

def get_db():
    return db

def get_auth():
    return auth

def get_fbauth():
    return fbauth

print('Initialized Pyrebase.')

if __name__ == '__main__':
    db = get_db()
    print(db)

    # Add a new doc in collection 'cities' with ID 'LA'
    db.collection(u'cities').document(u'LA').set({
        u'name': u'Los Angeles',
        u'state': u'CA',
        u'country': u'USA'
    })