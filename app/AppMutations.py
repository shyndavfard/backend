from flask_graphql_auth import create_access_token, create_refresh_token, mutation_jwt_refresh_token_required, \
    get_jwt_identity, mutation_jwt_required
from graphene import ObjectType, List, Mutation, String, Field, Boolean, Int
from werkzeug.security import generate_password_hash, check_password_hash
from .ProtectedFields import ProtectedBool, BooleanField, ProtectedString, StringField
from app.Fields import User, AppFeedback, Favourites, Tour, Question, Answer, TourFeedback, MuseumObject, MCQuestion, \
    MCAnswer, Checkpoint, PictureCheckpoint, ObjectCheckpoint
from models.User import User as UserModel
from models.Code import Code as CodeModel
from models.Tour import Tour as TourModel
from models.Answer import Answer as AnswerModel
from models.Question import Question as QuestionModel
from models.Favourites import Favourites as FavouritesModel
from models.MuseumObject import MuseumObject as MuseumObjectModel
from models.AppFeedback import AppFeedback as AppFeedbackModel
from models.TourFeedback import TourFeedback as TourFeedbackModel
from graphene_file_upload.scalars import Upload
from models.Picture import Picture as PictureModel
from models.Badge import Badge as BadgeModel
from models.MultipleChoiceQuestion import MultipleChoiceQuestion as MCQuestionModel
from models.MultipleChoiceAnswer import MultipleChoiceAnswer as MCAnswerModel
from models.ProfilePicture import ProfilePicture as ProfilePictureModel
from models.Checkpoint import Checkpoint as CheckpointModel
from models.PictureCheckpoint import PictureCheckpoint as PictureCheckpointModel
from models.ObjectCheckpoint import ObjectCheckpoint as ObjectCheckpointModel
"""
These are the mutations available in the App API. 
Tasks: - account creation 
       - login 
       - account management ( change password, delete account) 
       - manage favourite objects and tours 
       - provide feedback for the app 
       - created tours and questions 
       - set session ids 
       - join tours using the session id 
       - create and submit answers 
       - provide feedback for tours 
       
login returns access and refresh token. all other requests require a valid access token.  
"""


class CreateUser(Mutation):
    """Create a user account.
       Parameters: username, String, name of the account. has to be unique
                   password, String, password, no requirements, saved as a hash
       if successful returns the created user and ok=True
       fails if the username is already taken. returns Null and False in that case
    """

    class Arguments:
        username = String(required=True)
        password = String(required=True)

    user = Field(lambda: User)
    ok = Boolean()

    def mutate(self, info, username, password):
        # ensure there is no user with this name
        # making this check here prevents a mongoengine error but uniqueness of the name is also enforced in the model
        if not UserModel.objects(username=username):
            user = UserModel(username=username, password=generate_password_hash(password))
            user.save()
            return CreateUser(user=user, ok=True)
        else:
            return CreateUser(user=None, ok=False)


class AddBadgeProgress(Mutation):
    """Award a user a new achievement badge.
            Parameters: token, String, valid jwt access token of a user
                        badge_id, String, the internal id of the badge to be awarded
            if successful returns the updated user object and ok=True
            if unsuccessful because the token was invalid returns empty value for ok
            if unsuccessful because of invalid badge id returns Null and False
            is successful if called when the user already has unlocked the badge.
        """

    class Arguments:
        token = String()
        badge_id = String()
        progress = Int()

    ok = Field(ProtectedBool)
    user = Field(lambda: User)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, badge_id, progress):
        # get the user object to reference
        username = get_jwt_identity()
        user = UserModel.objects.get(username=username)
        # assert the badge exists
        if not BadgeModel.objects(id=badge_id):
            return AddBadgeProgress(user=None, ok=BooleanField(boolean=False))
        else:
            # check the user's current progress towards the badge
            badge = BadgeModel.objects.get(id=badge_id)
            user_progress = user.badge_progress
            current = user_progress[badge_id]
            # if the user progressed past the cost of the badge set the current progress to the badge cost
            if current + progress >= badge.cost:
                user_progress[badge_id] = badge.cost
                # award the user the badge if they do not already own it
                if badge not in user.badges:
                    badges = user.badges
                    badges.append(badge)
                    user.update(set__badges=badges)
                    user.save()
                    user.reload()
            else:
                user_progress[badge_id] = current + progress
            user.update(set__badge_progress=user_progress)
            user.save()
            return AddBadgeProgress(user=user, ok=BooleanField(boolean=True))


class PromoteUser(Mutation):
    """Use a promotion code to promote a user's account to producer status.
       Parameters: token, String, valid jwt access token of a user
                   code, String, 5 character string used as promotion password
        if successful returns the updated user object and ok=True
        if unsuccessful because the code was invalid returns Null and False
        if unsuccessful because the token was invalid returns empty value for ok
        """

    class Arguments:
        token = String()
        code = String()

    ok = Field(ProtectedBool)
    user = Field(User)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, code):
        username = get_jwt_identity()
        # assert the code is valid
        if not CodeModel.objects(code=code):
            return PromoteUser(ok=BooleanField(boolean=False), user=None)
        else:
            # get the code object in the database
            code_doc = CodeModel.objects.get(code=code)
            # delete code as they are one time use
            code_doc.delete()
            # get the user object
            user = UserModel.objects.get(username=username)
            # give the user producer access
            user.update(set__producer=True)
            user.save()
            user.reload()
            return PromoteUser(ok=BooleanField(boolean=True), user=user)


class ChangePassword(Mutation):
    """Change a user's password.
       Requires the user to be logged in.
       Parameters: token, String, valid jwt access token of a user
                   password, String, the NEW password
       if successful returns True
       if unsuccessful because the token is invalid returns an empty value
    """

    class Arguments:
        token = String()
        password = String()

    ok = Field(ProtectedBool)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, password):
        username = get_jwt_identity()
        user = UserModel.objects.get(username=username)
        user.update(set__password=generate_password_hash(password))
        user.save()
        return ChangePassword(ok=BooleanField(boolean=True))


class Auth(Mutation):
    """Login. Create a session and jwt access and refresh tokens.
       Parameters: username, String, the username of the account you wish to log in to
                   password, String, the password of the account. password is hashed and compared to the saved hash.
        if successful returns a jwt accessToken (String), a jwt refresh token (String) and True
        if unsuccessful because the user does not exist or the password was invalid returns Null Null and False"""

    class Arguments:
        username = String(required=True)
        password = String(required=True)

    access_token = String()
    refresh_token = String()
    ok = Boolean()

    @classmethod
    def mutate(cls, _, info, username, password):
        # assert the login data is valid
        if not (UserModel.objects(username=username) and check_password_hash(
                UserModel.objects.get(username=username).password, password)):
            return Auth(ok=False, access_token=None, refresh_token=None)
        else:
            # if login data was valid create and return jwt access and refresh tokens
            return Auth(access_token=create_access_token(username), refresh_token=create_refresh_token(username),
                        ok=True)


class Refresh(Mutation):
    """Refresh a user's access token.
       Parameter: refreshToken, String, valid jwt refresh token.
       if successful return a new jwt access token for the owner of the refresh token. this invalidates old access tokens.
       if unsuccessful because the refresh token was invalid returns Null
    """

    class Arguments(object):
        refresh_token = String()

    new_token = String()

    @classmethod
    @mutation_jwt_refresh_token_required
    def mutate(cls, info):
        current_user = get_jwt_identity()
        return Refresh(new_token=create_access_token(identity=current_user))


class ChooseProfilePicture(Mutation):
    """
        Allows a user to choose a profile picture from the pictures available on the server
        Parameters:
                token, String, valid jwt access token
                picture_id, String, valid object id of the ProfilePicture object on the server
        if successful returns true
        if unsuccessful because the picture id was invalid returns False
        if unsuccessful because the token was invalid returns empty value
        is successful if chosen picture is current picture
    """

    class Arguments:
        token = String(required=True)
        picture_id = String(required=True)

    ok = Field(ProtectedBool)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, picture_id):
        user = UserModel.objects.get(username=get_jwt_identity())
        if not ProfilePictureModel.objects(id=picture_id):
            return ChooseProfilePicture(ok=BooleanField(boolean=False))
        else:
            picture = ProfilePictureModel.objects.get(id=picture_id)
            user.update(set__profile_picture=picture)
            user.save()
            return ChooseProfilePicture(ok=BooleanField(boolean=True))


# TODO: rework


class DeleteAccount(Mutation):
    """Delete a user account.
       Deleting an account will also delete any tours, questions, answers and favourites created by this user.
       Parameter: token, String, valid jwt access token of the account to be deleted.
       returns True if successful
       returns Null if token was invalid
       """

    class Arguments:
        token = String(required=True)

    ok = Field(ProtectedBool)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info):
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            tours = TourModel.objects(owner=user)
            for tour in tours:
                for question in tour.questions:
                    question.delete()
                for answer in tour.answers:
                    answer.delete()
                tour.delete()
            answers = AnswerModel.objects(owner=user)
            for answer in answers:
                answer.delete()
            user.delete()
        return DeleteAccount(ok=BooleanField(boolean=True))


class SendFeedback(Mutation):
    """Send Feedback about the App to the admins. Feedback is anonymous.
        Feedback consists of a rating on a scale from 1-5 and a text review.
        Parameters: token, String, valid jwt access token of a user
                    rating, Int, rating on a scale of 1-5
                    review, String, text review / feedback
        returns the feedback object and True if successful
        returns Null and an empty value for ok if the token was invalid
        returns Null and False if the rating was not in the range of 1-5
    """

    class Arguments:
        token = String(required=True)
        review = String(required=True)
        rating = Int(required=True)

    ok = Field(ProtectedBool)
    feedback = Field(lambda: AppFeedback)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, review, rating):
        # assert that the rating is on the 1-5 scale
        if rating in range(1, 6):
            feedback = AppFeedbackModel(review=review, rating=rating)
            feedback.save()
            # after feedback has been created it will be available to read for admins
            return SendFeedback(ok=BooleanField(boolean=True), feedback=feedback)
        return SendFeedback(ok=BooleanField(boolean=False), feedback=None)


class AddFavouriteObject(Mutation):
    """Add an object to a user's favourites.
       Parameters: token, String, valid jwt access token of a user
                   objectId, String, inventory ID of the object to be added
       returns the list of favourites and True if successful
       returns Null and False if the object does not exist
       returns Null and an empty value for ok if the token was invalid """

    class Arguments:
        token = String(required=True)
        object_id = String(required=True)

    ok = Field(ProtectedBool)
    favourites = Field(lambda: Favourites)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, object_id):
        user = UserModel.objects.get(username=get_jwt_identity())
        if MuseumObjectModel.objects(object_id=object_id):
            museum_object = MuseumObjectModel.objects.get(object_id=object_id)
            if FavouritesModel.objects(user=user):
                favourites = FavouritesModel.object.get(user=user)
                if favourites.favourite_objects:
                    objects = favourites.favourite_objects
                    if museum_object not in objects:
                        objects.append(museum_object)
                        favourites.update(set__favourite_objects=objects)
                        favourites.save()
                else:
                    objects = [museum_object]
                    favourites.update(set__favourite_objects=objects)
                    favourites.save()
                favourites.reload()
                return AddFavouriteObject(ok=BooleanField(boolean=True), favourites=favourites)
            else:
                objects = [museum_object]
                favourites = FavouritesModel(user=user, favourite_objects=objects)
                favourites.save()
                return AddFavouriteObject(ok=BooleanField(boolean=True), favourites=favourites)
        else:
            return AddFavouriteObject(ok=BooleanField(boolean=False), favourites=None)


class RemoveFavouriteObject(Mutation):
    """Remove an object from a user's list of favourite objects.
      Parameters: token, String, valid jwt access token of a user
                   objectId, String, inventory ID of the object to be removed
       returns the updated list of favourites and True if successful
       returns None and False if the user does not have any favourites or object does not exist
       returns None and an empty value for ok if the token is invalid
       This operation works and is successful if the object supplied is not part of the user's favourites.
    """

    class Arguments:
        token = String(required=True)
        object_id = String(required=True)

    ok = Field(ProtectedBool)
    favourites = Field(lambda: Favourites)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, object_id):
        # get the user object to reference
        user = UserModel.objects.get(username=get_jwt_identity())
        # get the user's favourites
        if FavouritesModel.objects.get(user=user):
            favourites = FavouritesModel.objects.get(user=user)
            # assert the MuseumObject exists
            if MuseumObjectModel.objects(object_id=object_id):
                museum_object = MuseumObjectModel.objects.get(object_id=object_id)
                # if the object is in the user's favourites remove it
                if museum_object in favourites.favourite_objects:
                    objects = favourites.favourite_objects
                    objects.remove(museum_object)
                    favourites.update(set__favourite_objects=objects)
                    favourites.save()
                    favourites.reload()
                # operation if successful is the object was already not part of the user's favourites
                return RemoveFavouriteObject(ok=BooleanField(boolean=True), favourites=favourites)
        return RemoveFavouriteObject(ok=BooleanField(boolean=False), favourites=None)


class AddFavouriteTour(Mutation):
    """Add a tour to a user's list of favourite tours.
      Parameters: token, String, valid jwt access token of a user
                   tourId, String, document ID of the tour to be added
      returns the updated list of favourites and True if successful.
      returns Null and False if the tour does not exits
      returns Null and an empty value for ok is the token is invalid
    """

    class Arguments:
        token = String(required=True)
        tour_id = String(required=True)

    ok = Field(ProtectedBool)
    favourites = Field(lambda: Favourites)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id):
        # get user object to reference
        user = UserModel.objects.get(username=get_jwt_identity())
        # assert that tour exists and get the object to reference
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            # get the users current favourites
            if FavouritesModel.objects(user=user):
                favourites = FavouritesModel.objects.get(user=user)
                if favourites.favourite_tours:
                    tours = favourites.favourite_tours
                    # if the tour is not yet in the user's favourite tours add it
                    if tour not in tours:
                        tours.append(tour)
                        favourites.update(set__favourite_tours=tours)
                        favourites.save()
                # if the user did not have any favourite tours before create a new list and add the tour to it
                else:
                    tours = [tour]
                    favourites.update(set__favourite_tours=tours)
                    favourites.save()
                favourites.reload()
                return AddFavouriteTour(ok=BooleanField(boolean=True), favourites=favourites)
            # if the user did not have any favourites before create a new object and add the tour to favourite tours
            else:
                tours = [tour]
                favourites = FavouritesModel(user=user, favourite_tours=tours)
                favourites.save()
                return AddFavouriteTour(ok=BooleanField(boolean=True), favourites=favourites)
        else:
            return AddFavouriteTour(ok=BooleanField(boolean=False), favourites=None)


class RemoveFavouriteTour(Mutation):
    """Remove a tour to a user's list of favourite tours.
          Parameters: token, String, valid jwt access token of a user
                       tourId, String, document ID of the tour to be removed
          returns the updated list of favourites and True if successful.
          returns None and False if the user does not have any favourites or tour does not exist
          returns None and an empty value for ok if the token is invalid
       This operation works and is successful if the tour supplied is not part of the user's favourites.
        """

    class Arguments:
        token = String(required=True)
        tour_id = String(required=True)

    ok = Field(ProtectedBool)
    favourites = Field(lambda: Favourites)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id):
        # get user to reference
        user = UserModel.objects.get(username=get_jwt_identity())
        # get the user's favourites
        if FavouritesModel.objects.get(user=user):
            favourites = FavouritesModel.objects.get(user=user)
            # check if tour exists
            if TourModel.objects(id=tour_id):
                tour = TourModel.objects.get(id=tour_id)
                # check if tour is in the user's favourites. if it is remove it
                if tour in favourites.favourite_tours:
                    tours = favourites.favourite_tours
                    tours.remove(tour)
                    favourites.update(set__favourite_tours=tours)
                    favourites.save()
                    favourites.reload()
                # if the tour was not in the user's favourites the call is still successful
                return RemoveFavouriteTour(ok=BooleanField(boolean=True), favourites=favourites)
        return RemoveFavouriteTour(ok=BooleanField(boolean=False), favourites=None)


class CreateTour(Mutation):
    """ Create a tour
        Parameters: token, String, jwt access token of a user
                    name, String, name of the tour
                    session_id, Int, passcode used to join the tour
                    description, String, short description of the tour
                    difficulty, String, rating of difficulty on a scale of 1-5
                    search_id, String, id by which users can find the tour. has to be unique in the database
        can only be used by users whose 'producer' attribute is True
        if successful returns the created Tour object and "success"
        if unsuccessful because the owner of the token is not a producer returns Null and "user is not producer"
        if unsuccessful because the searchId is already taken returns Null and "search id already in use"
        if unsuccessful because the token is invalid returns an empty value for ok
    """

    class Arguments:
        token = String(required=True)
        name = String(required=True)
        session_id = Int(required=True)
        difficulty = Int(required=True)
        search_id = String(required=True)
        description = String()

    tour = Field(lambda: Tour)
    ok = Field(ProtectedString)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, name, session_id, difficulty, search_id, description=None):
        owner_name = get_jwt_identity()
        # get user object tot reference as owner
        if UserModel.objects(username=owner_name):
            owner = UserModel.objects.get(username=owner_name)
            # owner has to be producer to be allowed to create a tour
            if owner.producer:
                # owner is automatically the first member of the tour
                users = [owner]
                # ensure difficulty rating is on the scale
                if difficulty < 1:
                    difficulty = 1
                elif difficulty > 5:
                    difficulty = 5
                if not TourModel.objects(search_id=search_id):
                    tour = TourModel(owner=owner, name=name, users=users, session_id=session_id, difficulty=difficulty,
                                     description=description, search_id=search_id)
                    tour.save()
                    return CreateTour(tour=tour, ok=StringField(string="success"))
                else:
                    return CreateTour(tour=None, ok=StringField(string="search id already in use"))
        return CreateTour(tour=None, ok=StringField(string="User is not producer"))


class CreateCheckpoint(Mutation):
    """
        Creates a generic checkpoint i.e. a text-only checkpoint
        Parameters:
            token, String, valid jwt access token
            tour_id, String, object id of a valid tour
            text, String, optional, text on the checkpoint
        caller has to be owner of tour
        if successful returns the created checkpoint and True
        if unsuccessful because the tour did not exist or the caller did not own the tour returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok
    """
    class Arguments:
        token = String(required=True)
        tour_id = String(required=True)
        text = String()

    checkpoint = Field(lambda: Checkpoint)
    ok = Field(ProtectedBool)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, **kwargs):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
        else:
            return CreateCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        user = UserModel.objects.get(username=get_jwt_identity())
        if not user == tour.owner:
            return CreateCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        checkpoint = CheckpointModel(tour=tour)
        text = kwargs.get('text', None)
        if text is not None:
            checkpoint.update(set__text=text)
        checkpoint.save()
        return CreateCheckpoint(checkpoint=checkpoint, ok=BooleanField(boolean=True))


class CreatePictureCheckpoint(Mutation):
    """
        Creates a Picture Checkpoint
        Parameters:
            token, String, valid jwt access token
            tour_id, String, object id of a valid tour
            text, String, optional, text on the checkpoint
            picture_id, String, optional, id of an existing picture in the database to turn into a checkpoint
            picture, Upload, optional, image in png format to create a checkpoint with a new image
            picture_description, String, optional, description of the uploaded picture (NOT of the checkpoint)
        caller has to be owner of tour
        if successful returns the created checkpoint and True
        if unsuccessful because the tour did not exist or the caller did not own the tour or the picture id was invalid
            returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok
    """
    class Arguments:
        token = String(required=True)
        tour_id = String(required=True)
        picture_id = String()
        picture = Upload()
        picture_description = String()
        text = String()

    checkpoint = Field(lambda: PictureCheckpoint)
    ok = Field(ProtectedBool)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, **kwargs):
        if TourModel.object(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
        else:
            return CreatePictureCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        user = UserModel.objects.get(get_jwt_identity())
        if not user == tour.owner:
            return CreatePictureCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        picture_id = kwargs.get('picture_id', None)
        picture = kwargs.get('picture', None)
        picture_description = kwargs.get('picture_description', None)
        text = kwargs.get('text', None)
        if picture_id is not None:
            if PictureModel(id=picture_id):
                pic = PictureModel(id=picture_id)
                checkpoint = PictureCheckpointModel(picture=pic, tour=tour, text=text)
                checkpoint.save()
                return CreatePictureCheckpoint(checkpoint=checkpoint, ok=BooleanField(boolean=True))
            else:
                return CreatePictureCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        if picture is not None:
            x = PictureModel(description=picture_description)
            x.picture.put(picture, content_type='image/png')
            x.save()
            checkpoint = PictureCheckpointModel(picture=x, tour=tour, text=text)
            checkpoint.save()
            return CreatePictureCheckpoint(checkpoint=checkpoint, ok=BooleanField(boolean=True))


class CreateObjectCheckpoint(Mutation):
    class Arguments:
        token = String(required=True)
        tour_id = String(required=True)
        object_id = String(required=True)
        text = String()

    ok = Field(ProtectedBool)
    checkpoint = Field(lambda: ObjectCheckpoint)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, object_id, text=None):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
        else:
            return CreateObjectCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        user = UserModel.objects.get(username=get_jwt_identity())
        if not user == tour.owner:
            return CreateObjectCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        if not MuseumObjectModel.objects(object_id=object_id):
            return CreateObjectCheckpoint(checkpoint=None, ok=BooleanField(boolean=False))
        museum_object = MuseumObjectModel.objects.get(object_id=object_id)
        checkpoint = ObjectCheckpointModel(tour=tour, museum_object=museum_object, text=text)
        checkpoint.save()
        return CreateObjectCheckpoint(checkpoint=checkpoint, ok=BooleanField(boolean=True))


class CreateAnswer(Mutation):
    class Arguments:
        token = String(required=True)
        answer = String(required=True)
        question = String(required=True)

    answer = Field(lambda: Answer)
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, answer, question):
        # get user object to reference
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            # assert question exists
            if QuestionModel.objects(id=question):
                question = QuestionModel.objects.get(id=question)
            else:
                return CreateAnswer(answer=None, ok=BooleanField(boolean=False))
            # creating and submitting a new answer
            if not AnswerModel.objects(question=question, user=user):
                answer = AnswerModel(question=question, user=user, answer=answer)
                answer.save()
                return CreateAnswer(answer=answer, ok=BooleanField(boolean=True))
            # if the user previously answered the question update the answer
            else:
                prev = AnswerModel.objects.get(question=question, user=user)
                prev.update(set__answer=answer)
                prev.reload()
                return CreateAnswer(answer=prev, ok=BooleanField(boolean=True))
        else:
            return CreateAnswer(answer=None, ok=BooleanField(boolean=False))


class CreateMCAnswer(Mutation):
    """
        Creating and submitting a multiple choice answer. Answer may only be submitted once and is immediately evaluated
        Parameters:
            token, String, valid jwt access token
            question, id of a multiple choice question
            answer, List of Int, indices of the correct answers in the question.possible_answers
        if successful returns the answer, ok=True and the number of correct answers
        if unsuccessful because the token was invalid returns empty value for ok
        if unsuccessful because the question did not exist returns Null and False
        if unsuccessful because the number of submitted answers was too high returns Null False and -1 for correct
    """

    class Arguments:
        token = String(required=True)
        answer = List(of_type=Int, required=True)
        question = String(required=True)

    answer = Field(lambda: MCAnswer)
    correct = Int()
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, answer, question):
        # get user object to reference
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            # assert question exists
            if QuestionModel.objects(id=question):
                question = MCQuestionModel.objects.get(id=question)
            else:
                return CreateAnswer(answer=None, ok=BooleanField(boolean=False), correct=0)
            # creating and submitting a new answer
            if not MCAnswerModel.objects(question=question, user=user):
                # number of answers may not be more than permitted by the question
                if len(answer) <= question.max_choices:
                    correct = 0
                    correct_answers = question.correct_answers
                    for single_answer in answer:
                        if single_answer in correct_answers:
                            correct += 1
                    answer = MCAnswerModel(question=question, user=user, answer=answer)
                    answer.save()
                    return CreateMCAnswer(answer=answer, ok=BooleanField(boolean=True), correct=correct)
                else:
                    return CreateMCAnswer(answer=None, ok=BooleanField(boolean=False), correct=-1)
        return CreateMCAnswer(answer=None, ok=BooleanField(boolean=False), correct=0)


class CreateQuestion(Mutation):
    class Arguments:
        token = String(required=True)
        linked_objects = List(of_type=String)
        question_text = String(required=True)
        tour_id = String(required=True)

    question = Field(lambda: Question)
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, question_text, tour_id, linked_objects=[]):
        # get the current user object to check for permissions
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            # assert that tour exists
            if TourModel.objects(id=tour_id):
                tour = TourModel.objects.get(id=tour_id)
                # assert user is owner of the tour
                if tour.owner == user:
                    question = QuestionModel(linked_objects=linked_objects,
                                             question=question_text, tour=tour)
                    question.save()
                    return CreateQuestion(question=question,
                                          ok=BooleanField(boolean=True))

        return CreateQuestion(question=None, ok=BooleanField(boolean=False))


class CreateMCQuestion(Mutation):
    class Arguments:
        token = String(required=True)
        linked_objects = List(of_type=String)
        question_text = String(required=True)
        possible_answers = List(of_type=String, required=True)
        correct_answers = List(of_type=Int, required=True)
        max_choices = Int(required=True)
        tour_id = String(required=True)

    question = Field(lambda: MCQuestion)
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, question_text, possible_answers, correct_answers, max_choices, tour_id, linked_objects=[]):
        # get the current user object to check for permissions
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            # assert that tour exists
            if TourModel.objects(id=tour_id):
                tour = TourModel.objects.get(id=tour_id)
                # assert user is owner of the tour
                if tour.owner == user:
                    question = MCQuestionModel(linked_objects=linked_objects,
                                               question=question_text, possible_answers=possible_answers,
                                               correct_answers=correct_answers, max_choices=max_choices, tour=tour)
                    question.save()
                    return CreateMCQuestion(question=question,
                                            ok=BooleanField(boolean=True))

        return CreateMCQuestion(question=None, ok=BooleanField(boolean=False))


class AddMember(Mutation):
    """Join a Tour using its session code.
       Parameters: token, String, access token of a user
                   tour_id, String, document id of an existing Tour object
                   session_id, Int, current session id of the tour
       if successful returns the Tour object the user joined and a Boolean True
       if unsuccessful because the Tour does not exist or the session code is invalid returns Null and False
       if unsuccessful because the token was invalid returns an empty value for ok
    """

    class Arguments:
        tour_id = String(required=True)
        token = String(required=True)
        session_id = Int(required=True)

    ok = Field(ProtectedBool)
    tour = Field(lambda: Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, session_id):
        # assert tour exists
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            # assert the provided session id is valid for the tour
            if tour.session_id == session_id:
                username = get_jwt_identity()
                # get user object to reference in the users list of the tour
                if UserModel.objects(username=username):
                    user = UserModel.objects.get(username=username)
                    users = tour.users
                    # add user to tour
                    if user not in users:
                        users.append(user)
                        tour.update(set__users=users)
                        tour.save()
                        tour.reload()
                    # if the user was already a member of the tour nothing changes and the call is still successful
                    return AddMember(ok=BooleanField(boolean=True), tour=tour)
                else:
                    return AddMember(ok=BooleanField(boolean=False), tour=None)
            else:
                return AddMember(ok=BooleanField(boolean=False), tour=None)
        else:
            return AddMember(ok=BooleanField(boolean=False), tour=None)


class SubmitReview(Mutation):
    """Submit a tour for review by the administrators.
    Parameters: token, String, access token of a user, owner must be the creator of the tour
                tour_id, String, document id of an existing Tour
    if successful returns the Tour object and a Boolean True
    if unsuccessful because the Tour does not exist or the token does not belong to the owner of
        the tour returns Null and False
    if unsuccessful because the token was invalid returns an empty value for ok
    """

    class Arguments:
        tour_id = String(required=True)
        token = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(lambda: Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id):
        # assert tour exists
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            username = get_jwt_identity()
            # assert user is the owner of the tour
            if tour.owner.username == username:
                # setting status of the tour to pending will make the request for review show up for admins
                tour.update(set__status='pending')
                tour.save()
                tour.reload()
                return SubmitReview(ok=BooleanField(boolean=True), tour=tour)
            else:
                return SubmitReview(ok=BooleanField(boolean=False), tour=None)
        else:
            return SubmitReview(ok=BooleanField(boolean=False), tour=None)


class UpdateSessionId(Mutation):
    """Change the session id of a tour.
       Parameters: token, String, access token of a user, owner must be the owner of the tour
                   tour, String, document id of an existing Tour owned by the owner of the token
                   session_id, Int, value the session id should be updated to
       if successful returns the Tour and a Boolean True
       if unsuccessful because the Tour does not exist or the token does not belong to the owner of the tour
            returns Null and False
       if unsuccessful because the token was invalid returns an empty value for ok
       """

    class Arguments:
        token = String(required=True)
        tour = String(required=True)
        session_id = Int(required=True)

    ok = Field(ProtectedBool)
    tour = Field(lambda: Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour, session_id):
        # assert tour exists
        if TourModel.objects(id=tour):
            tour = TourModel.objects.get(id=tour)
            username = get_jwt_identity()
            # assert caller is the owner of the tour
            if tour.owner.username == username:
                tour.update(set__session_id=session_id)
                tour.save()
                tour.reload()
                return UpdateSessionId(tour=tour, ok=BooleanField(boolean=True))
            else:
                return UpdateSessionId(tour=None, ok=BooleanField(boolean=False))
        else:
            return UpdateSessionId(tour=None, ok=BooleanField(boolean=False))


class RemoveUser(Mutation):
    class Arguments:
        """Kick a user from a Tour.
        Parameters: token, String, access token of a user, owner must be the creator of the tour
                   tour_id, String, document id of an existing Tour
                   username, String, name of the user to be removed
        if successful returns the updated Tour object and a Boolean True
            note this operation is successful if the user was already not part of the tour
        if unsuccessful because the Tour does not exist or the token does not belong to the owner of
            the tour or the username does not exist returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok

        """
        token = String(required=True)
        tour_id = String(required=True)
        username = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(lambda: Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, username):
        # assert tour exists
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            owner = get_jwt_identity()
            # assert caller is the owner of the tour
            if tour.owner.username == owner:
                # assert the user the caller wants to kick exists
                if UserModel.objects(username=username):
                    user = UserModel.objects.get(username=username)
                    users = tour.users
                    # if user is a member remove him
                    if user in users:
                        users.remove(user)
                    # if the user was not a member of the tour nothing changes and the function call is still successful
                    tour.update(set__users=users)
                    tour.save()
                    tour.reload()
                    return RemoveUser(tour=tour, ok=BooleanField(boolean=True))
                else:
                    return RemoveUser(tour=None, ok=BooleanField(boolean=False))
            else:
                return RemoveUser(tour=None, ok=BooleanField(boolean=False))
        else:
            return RemoveUser(tour=None, ok=BooleanField(boolean=False))


class SubmitFeedback(Mutation):
    """Submit feedback for a Tour.
    Parameters: token, String, access token of a user
                   tour_id, String, document id of an existing Tour
                   rating, Int, rating on a scale of 1-5
                   review, String, text review for the tour
        Feedback is anonymous i.e. the user is submitting the feedback is not logged
        Also note that a user has to be part of a tour in order to submit feedback about it
        if successful returns the Feedback object and a Boolean True
        if unsuccessful because the Tour does not exist or the user does not exits or is not a member of the tour
            or the rating value is invalid returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok """

    class Arguments:
        tour_id = String(required=True)
        token = String(required=True)
        rating = Int(required=True)
        review = String(required=True)

    ok = Field(ProtectedBool)
    feedback = Field(lambda: TourFeedback)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, rating, tour_id, review):
        # assert tour exists
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            # get user object to use as reference in the feedback
            if UserModel.objects(username=get_jwt_identity()):
                user = UserModel.objects.get(username=get_jwt_identity())
                if user in tour.users:
                    # assert rating is valid on the 1-5 scale
                    if rating in range(1, 6):
                        feedback = TourFeedbackModel(rating=rating, review=review, tour=tour)
                        feedback.save()
                        return SubmitFeedback(ok=BooleanField(boolean=True), feedback=feedback)
                    else:
                        return SubmitFeedback(ok=BooleanField(boolean=False), feedback=None)
                else:
                    return SubmitFeedback(ok=BooleanField(boolean=False), feedback=None)
            else:
                return SubmitFeedback(ok=BooleanField(boolean=False), feedback=None)
        else:
            return SubmitFeedback(ok=BooleanField(boolean=False), feedback=None)


# TODO: to be removed, does nothing
class FileUpload(Mutation):
    class Arguments:
        file = Upload(required=True)

    success = Boolean()

    def mutate(self, info, file, **kwargs):
        pic = PictureModel(description='gqql')
        pic.picture.put(file, content_type='image/png')
        pic.save()
        return FileUpload(success=True)


class Mutation(ObjectType):
    create_user = CreateUser.Field()
    auth = Auth.Field()
    refresh = Refresh.Field()
    change_password = ChangePassword.Field()
    promote_user = PromoteUser.Field()
    delete_account = DeleteAccount.Field()
    add_favourite_tour = AddFavouriteTour.Field()
    remove_favourite_tour = RemoveFavouriteTour.Field()
    add_favourite_object = AddFavouriteObject.Field()
    remove_favourite_object = RemoveFavouriteObject.Field()
    app_feedback = SendFeedback.Field()
    create_tour = CreateTour.Field()
    create_question = CreateQuestion.Field()
    create_answer = CreateAnswer.Field()
    create_mc_answer = CreateMCAnswer.Field()
    create_mc_question = CreateMCQuestion.Field()
    add_member = AddMember.Field()
    submit_for_review = SubmitReview.Field()
    update_session_id = UpdateSessionId.Field()
    remove_user = RemoveUser.Field()
    submit_tour_feedback = SubmitFeedback.Field()
    file_upload = FileUpload.Field()
    add_badge_progress = AddBadgeProgress.Field()
    choose_profile_picture = ChooseProfilePicture.Field()
    create_checkpoint = CreateCheckpoint.Field()
    create_picture_checkpoint = CreatePictureCheckpoint.Field()
    create_object_checkpoint = CreateObjectCheckpoint.Field()