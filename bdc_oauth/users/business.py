from copy import deepcopy
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import InternalServerError, NotFound, Conflict, Forbidden

from bdc_oauth.utils.base_mongo import mongo

class UsersBusiness():

    @classmethod
    def init_infos(cls): 
        return {
            "model": mongo.db.users
        }

    @classmethod
    def get_all(cls):
        model = cls.init_infos()['model']

        users = model.find({"deleted_at": None}, {"credential.password": 0})
        return list(users)

    @classmethod
    def get_by_id(cls, id, return_password=0):
        model = cls.init_infos()['model']

        try:
            user = model.find_one({"_id": ObjectId(id), "deleted_at": None}, {"credential.password": return_password})
            return user
        except Exception:
            raise NotFound("Client not Found!")

    @classmethod
    def create(cls, infos_user):
        model = cls.init_infos()['model']
        
        """ 
        verifica se já existe um usuário com o mesmo e-mail cadastrado
        """
        user_exits = model.find_one({"email": infos_user["email"], "deleted_at": None})
        if user_exits:
            raise Conflict('Email already registered in the system!')

        infos_user['created_at'] = datetime.now()
        infos_user['deleted_at'] = None

        """ 
        adiciona as credenciais no objeto user
        """
        credentials = {
            "username": deepcopy(infos_user['email']),
            "password": generate_password_hash(infos_user['password']),
            "grants": ["user"]
        }
        infos_user['credential'] = credentials
        infos_user['clients_authorized'] = []

        """ 
        salva no mongodb
        """
        try:
            model.insert_one(infos_user)
            return infos_user
            
        except Exception:
            return False

    @classmethod
    def update(cls, id, infos_user):
        model = cls.init_infos()['model']
        
        """ 
        verifica se existe o usuário no banco
        """
        user = cls.get_by_id(id)
        if not user:
            raise NotFound('User not Found!')

        """ 
        salva no mongodb 
        """
        try:
            model.update_one({"_id": ObjectId(id)}, {"$set": infos_user})
            return True
        except Exception:
            return False      


    @classmethod
    def delete(cls, id):
        model = cls.init_infos()['model']

        user = cls.get_by_id(id)
        if not user:
            raise NotFound('User not Found!')

        user['deleted_at'] = datetime.now()  
        try:
            model.update_one({"_id": ObjectId(id)}, {"$set": user})
            return True
        except Exception as e:
            raise InternalServerError("Deleting user error!")
    

    @classmethod
    def change_password(cls, id, password, new_password):
        model = cls.init_infos()['model']

        user = cls.get_by_id(id, return_password=1)
        if not user:
            raise NotFound('User not Found!')

        if check_password_hash(user['credential']['password'], password) is False:
            raise Forbidden('Incorrent current password!')

        try:
            new_pass = generate_password_hash(new_password)
            model.update_one({"_id": ObjectId(id)}, {"$set": {"credential.password": new_pass}})
            return True
        except Exception:
            return False

    @classmethod
    def list_clients_authorized(cls, id):
        model = cls.init_infos()['model']

        clients = model.aggregate([ 
            {
                "$unwind": "$clients_authorized"
            },
            { 
                "$lookup": {
                    "from": "clients",
                    "localField": "clients_authorized",
                    "foreignField": "_id",
                    "as": "clients"
                }
            },
            {
                "$match": {
                    "_id": ObjectId(id), 
                    "deleted_at": None,
                    "$or": [
                        { "clients.expired_at": None },
                        { "clients.expired_at": { "$gt": datetime.now() } }
                    ]
                }
            }, 
            {
                "$project": {
                    "_id": 0,
                    "clients": 1
                }
            }
        ])
        return list(clients)