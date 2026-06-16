from bson import ObjectId

def transform_id(id: str or ObjectId):
    _id = id
    if isinstance(id, str) and ObjectId.is_valid(id):
        _id = ObjectId(id)
    return _id