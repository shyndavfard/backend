from flask_graphql_auth import mutation_jwt_required, get_jwt_identity, query_jwt_required
from graphene import Mutation, String, List, Int, Field, Schema, ObjectType
from app.ProtectedFields import ProtectedBool
from app.ProtectedFields import BooleanField
from models.User import User as UserModel
from models.Tour import Tour as TourModel
from models.MuseumObject import MuseumObject as MuseumObjectModel
from models.Question import Question as QuestionModel
from models.Answer import Answer as AnswerModel
from models.TourFeedback import TourFeedback as TourFeedbackModel
from app.Fields import Tour, Question, Answer, TourFeedback, MuseumObject

"""
    Schema for the creation and management of tours 
    bound to endpoint /tour/ 
    Tour functions: 
        create tour 
        add object
        remove object 
        add question 
        remove question
        submit answer 
        change session code 
        join tour with session code 
        query joined tours 
        query owned tours 
        submit a tour for review 
    Question / Answer functions:
        create questions and answers 
        submit answers to questions 
        mark answers as correct/incorrect 
        
"""


class CreateTour(Mutation):
    """ Create a tour
        Parameters: token, String, jwt access token of a user
                    name, String, name of the tour
                    session_id, Int, passcode used to join the tour
        can only be used by users whose 'producer' attribute is True
        if successful returns the created Tour object and a Boolean True
        if unsuccessful because the owner of the token is not a producer returns Null and False
        if unsuccessful because the token is invalid returns an empty value for ok
    """

    class Arguments:
        token = String(required=True)
        name = String(required=True)
        session_id = Int(required=True)

    tour = Field(lambda: Tour)
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, name, session_id):
        owner_name = get_jwt_identity()
        if UserModel.objects(username=owner_name):
            owner = UserModel.objects.get(username=owner_name)
            if owner.producer:
                users = [owner]
                tour = TourModel(owner=owner, name=name, users=users, session_id=session_id)
                tour.save()
                return CreateTour(tour=tour, ok=BooleanField(boolean=True))
            else:
                return CreateTour(tour=None, ok=BooleanField(boolean=False))


class CreateAnswer(Mutation):
    class Arguments:
        token = String(required=True)
        answer = String(required=True)
        question = String(required=True)

    answer = Field(Answer)
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, answer, question):
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            if QuestionModel.objects(id=question):
                question = QuestionModel.objects.get(id=question)
            else:
                return CreateAnswer(answer=None, ok=BooleanField(boolean=False))
            if not AnswerModel.objects(question=question, user=user):
                answer = AnswerModel(question=question, user=user, answer=answer)
                answer.save()
                return CreateAnswer(answer=answer, ok=BooleanField(boolean=True))
            else:
                prev = AnswerModel.objects.get(question=question, user=user)
                prev.update(set__answer=answer)
                prev.reload()
                return CreateAnswer(answer=prev, ok=BooleanField(boolean=True))
        else:
            return CreateAnswer(answer=None, ok=BooleanField(boolean=False))


class CreateQuestion(Mutation):
    class Arguments:
        token = String(required=True)
        linked_objects = List(of_type=String)
        question_text = String(required=True)

    question = Field(Question)
    ok = ProtectedBool()

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, question_text, linked_objects):
        username = get_jwt_identity()
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            if user.producer:
                question = QuestionModel(linked_objects=linked_objects,
                                         question=question_text)
                question.save()
                return CreateQuestion(question=question,
                                      ok=BooleanField(boolean=True))

            else:
                return CreateQuestion(question=None, ok=BooleanField(boolean=False))


class AddObject(Mutation):
    """Add an object to a tour
       Parameters:  token, String, access token of a user
                    tour_id, String, document id of an existing Tour document in the database, tour has to be created by
                                    the owner of the token
                    object_id, String, museum inventory number of an object that exists in the database
        if successful returns the updated Tour object and a Boolean True
        if unsuccessful because the tour_id or object_id was invalid or because the owner of the token does not own the
            tour returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok
    """

    class Arguments:
        tour_id = String(required=True)
        object_id = String(required=True)
        token = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, object_id):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            if tour.owner.username == get_jwt_identity():
                if MuseumObjectModel.objects(object_id=object_id):
                    museum_object = MuseumObjectModel.objects.get(object_id=object_id)
                    referenced = tour.referenced_objects
                    referenced.append(museum_object)
                    tour.update(set__referenced_objects=referenced)
                    tour.save()
                    tour = TourModel.objects.get(id=tour_id)
                    return AddObject(ok=BooleanField(boolean=True), tour=tour)
                else:
                    return AddObject(ok=BooleanField(boolean=False), tour=None)
            else:
                return AddObject(ok=BooleanField(boolean=False), tour=None)
        else:
            return AddObject(ok=BooleanField(boolean=False), tour=None)


class AddQuestion(Mutation):
    class Arguments:
        tour_id = String(required=True)
        question = String(required=True)
        token = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, question):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            if tour.owner.username == get_jwt_identity():
                if QuestionModel.objects(id=question):
                    question = QuestionModel.objects.get(id=question)
                    questions = tour.questions
                    questions.append(question)
                    tour.update(set__questions=questions)
                    tour.save()
                    tour = TourModel.objects.get(id=tour_id)
                    return AddQuestion(ok=BooleanField(boolean=True), tour=tour)
                else:
                    return AddQuestion(ok=BooleanField(boolean=False), tour=None)
            else:
                return AddQuestion(ok=BooleanField(boolean=False), tour=None)
        else:
            return AddQuestion(ok=BooleanField(boolean=False), tour=None)


class AddAnswer(Mutation):
    class Arguments:
        answer_id = String(required=True)
        tour_id = String(required=True)
        question_id = String(required=True)
        token = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, question_id, answer_id):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            username = get_jwt_identity()
            if UserModel.objects(username=username):
                user = UserModel.objects.get(username=username)
                if user in tour.users:
                    answers = tour.answers
                    if question_id in answers.keys():
                        answers[question_id].update({user.username: answer_id})
                    else:
                        answers[question_id] = {user.username: answer_id}
                    tour.update(set__answers=answers)
                    tour.save()
                    tour.reload()
                    return AddAnswer(tour=tour, ok=BooleanField(boolean=True))
                else:
                    return AddAnswer(tour=None, ok=BooleanField(boolean=False))
            else:
                return AddAnswer(tour=None, ok=BooleanField(boolean=False))
        else:
            return AddAnswer(tour=None, ok=BooleanField(boolean=False))


class AddMember(Mutation):
    """Join a Tour using it's session code.
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
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, session_id):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            if tour.session_id == session_id:
                username = get_jwt_identity()
                if UserModel.objects(username=username):
                    user = UserModel.objects.get(username=username)
                    users = tour.users
                    if user not in users:
                        users.append(user)
                        tour.update(set__users=users)
                        tour.save()
                        tour.reload()
                        return AddMember(ok=BooleanField(boolean=True), tour=tour)
                    else:
                        return AddMember(ok=BooleanField(boolean=False), tour=None)
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
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            username = get_jwt_identity()
            if tour.owner.username == username:
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
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour, session_id):
        if TourModel.objects(id=tour):
            tour = TourModel.objects.get(id=tour)
            username = get_jwt_identity()
            if tour.owner.username == username:
                tour.update(set__session_id=session_id)
                tour.save()
                tour.reload()
                return UpdateSessionId(tour=tour, ok=BooleanField(boolean=True))
            else:
                return UpdateSessionId(tour=None, ok=BooleanField(boolean=False))
        else:
            return UpdateSessionId(tour=None, ok=BooleanField(boolean=False))


class RemoveMuseumObject(Mutation):
    """Remove an Object from a Tour.
       Parameters: token, String, access token of a user, owner must be the creator of the tour
                   tour_id, String, document id of an existing Tour
                   object_id, String, museum inventory number of the object to be removed
        if successful returns the updated Tour object and a Boolean True
            note this operation is successful if the object was already not referenced in the tour
        if unsuccessful because the Tour does not exist or the token does not belong to the owner of
            the tour or the object does not exist returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok
    """

    class Arguments:
        token = String(required=True)
        tour = String(required=True)
        object_id = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour, object_id):
        if TourModel.objects(id=tour):
            tour = TourModel.objects.get(id=tour)
            username = get_jwt_identity()
            if tour.owner.username == username:
                if MuseumObjectModel.objects(object_id=object_id):
                    museum_object = MuseumObjectModel.objects.get(object_id=object_id)
                    referenced = tour.referenced_objects
                    if museum_object in referenced:
                        referenced.remove(museum_object)
                    tour.update(set__referenced_objects=referenced)
                    tour.save()
                    tour.reload()
                    return RemoveMuseumObject(tour=tour, ok=BooleanField(boolean=True))
                else:
                    return RemoveMuseumObject(tour=None, ok=BooleanField(boolean=False))
            else:
                return RemoveMuseumObject(tour=None, ok=BooleanField(boolean=False))
        else:
            return RemoveMuseumObject(tour=None, ok=BooleanField(boolean=False))


class RemoveQuestion(Mutation):
    """Remove a Question from a Tour.
       Parameters: token, String, access token of a user, owner must be the creator of the tour
                   tour_id, String, document id of an existing Tour
                   question_id, String, document id of the question to be removed
       if successful returns the Tour object and a Boolean True
            note this operation is successful if the question was already not referenced in the tour
        if unsuccessful because the Tour does not exist or the token does not belong to the owner of
            the tour or the question does not exist returns Null and False
        if unsuccessful because the token was invalid returns an empty value for ok
    """

    class Arguments:
        token = String(required=True)
        tour_id = String(required=True)
        question_id = String(required=True)

    ok = Field(ProtectedBool)
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, question_id):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            username = get_jwt_identity()
            if tour.owner.username == username:
                if QuestionModel.objects(id=question_id):
                    question = QuestionModel.objects.get(id=question_id)
                    questions = tour.questions
                    if question in questions:
                        questions.remove(question)
                        question.delete()
                    tour.update(set__questions=questions)
                    tour.save()
                    tour.reload()
                    answers = tour.answers
                    for answer in answers:
                        if answer.question == question:
                            answers.remove(answer)
                            answer.delete()
                            tour.update(set__answers=answers)
                    tour.save()
                    tour.reload()
                    return RemoveQuestion(tour=tour, ok=BooleanField(boolean=True))
                else:
                    return RemoveQuestion(tour=None, ok=BooleanField(boolean=False))
            else:
                return RemoveQuestion(tour=None, ok=BooleanField(boolean=False))
        else:
            return RemoveQuestion(tour=None, ok=BooleanField(boolean=False))


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
    tour = Field(Tour)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, tour_id, username):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            owner = get_jwt_identity()
            if tour.owner.username == owner:
                if UserModel.objects(username=username):
                    user = UserModel.objects.get(username=username)
                    users = tour.users
                    if user in users:
                        users.remove(user)
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
    feedback = Field(TourFeedback)

    @classmethod
    @mutation_jwt_required
    def mutate(cls, _, info, rating, tour_id, review):
        if TourModel.objects(id=tour_id):
            tour = TourModel.objects.get(id=tour_id)
            if UserModel.objects(username=get_jwt_identity()):
                user = UserModel.objects.get(username=get_jwt_identity())
                if user in tour.users:
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


class Mutation(ObjectType):
    create_tour = CreateTour.Field()
    create_question = CreateQuestion.Field()
    create_answer = CreateAnswer.Field()
    add_question = AddQuestion.Field()
    add_answer = AddAnswer.Field()
    add_object = AddObject.Field()
    add_member = AddMember.Field()
    submit_review = SubmitReview.Field()
    update_session_id = UpdateSessionId.Field()
    remove_museum_object = RemoveMuseumObject.Field()
    remove_question = RemoveQuestion.Field()
    remove_user = RemoveUser.Field()
    submit_feedback = SubmitFeedback.Field()


class Query(ObjectType):
    # queries related to tours
    """Query a specific Tour. Must be a member of the Tour.
       Parameters: token, String, access token of a user
                   tour_id, String, document id of an existing tour the owner of the token is a member of
       if successful returns the Tour
       if unsuccessful because the tour does not exist or the user is not a member of the tour returns Null and False
       if unsuccessful because the toke is invalid returns an empty value for ok
        """
    tour = List(Tour, token=String(), tour=String())
    """ Returns all tours a user is a Member of."""
    my_tours = List(Tour, token=String())
    """Returns all tours a user has created."""
    owned_tours = List(Tour, token=String())
    """Returns all feedback submitted for a tour. Can only be queried by the Tour owner."""
    feedback = List(TourFeedback, token=String(), tour=String())

    @classmethod
    @query_jwt_required
    def resolve_my_tours(cls, _, info):
        username = get_jwt_identity()
        user = UserModel.objects.get(username=username)
        return list(TourModel.objects(users__contains=user))

    @classmethod
    @query_jwt_required
    def resolve_tour(cls, _, info, tour):
        username = get_jwt_identity()
        user = UserModel.objects.get(username=username)
        tour = TourModel.objects.get(id=tour)
        if user in tour.users:
            return [tour]
        else:
            return []

    @classmethod
    @query_jwt_required
    def resolve_owned_tours(cls, _, info):
        username = get_jwt_identity()
        user = UserModel.objects.get(username=username)
        return list(TourModel.objects(owner=user))

    @classmethod
    @query_jwt_required
    def resolve_feedback(cls, _, info, tour):
        user = UserModel.objects.get(username=get_jwt_identity())
        if TourModel.objects(id=tour):
            tour = TourModel.objects.get(id=tour)
        if tour.owner == user:
            return list(TourFeedbackModel.objects(tour=tour))
        else:
            return []

    # queries related to questions and answers
    answers_to_question = List(Question, token=String(), question=String())
    answers_by_user = List(Answer, tour=String(), token=String(), user=String())
    my_answers = List(Answer, token=String(), tour=String())

    @classmethod
    @query_jwt_required
    def resolve_answers_to_question(cls, _, info, question):
        if QuestionModel.objects(id=question):
            question = QuestionModel.objects.get(id=question)
            return list(AnswerModel.objects(question=question))
        else:
            return None

    # TODO: when adding public and private answers gate private answers to the tour owner

    @classmethod
    @query_jwt_required
    def resolve_answers_by_user(cls, _, info, username, tour):
        if UserModel.objects(username=username):
            user = UserModel.objects.get(username=username)
            if TourModel.objects(id=tour):
                tour = TourModel.objects.get(id=tour)
                answers = []
                for answer in tour.answers:
                    if answer.user == user:
                        answers.append(answer)
                return answers
        return None

    @classmethod
    @query_jwt_required
    def resolve_my_answers(cls, _, info, tour):
        if TourModel.objects(id=tour):
            tour = TourModel.objects.get(id=tour)
            user = UserModel.objects.get(username=get_jwt_identity())
            answers = []
            for answer in tour.answers:
                if answer.user == user:
                    answers.append(answer)
            return answers
        return None

    # master query for objects
    museum_object = List(MuseumObject, object_id=String(),
                         category=String(),
                         sub_category=String(),
                         title=String(),
                         token=String(required=True),
                         year=String(),
                         picture=String(),
                         art_type=String(),
                         creator=String(),
                         material=String(),
                         size=String(),
                         location=String(),
                         description=String(),
                         interdisciplinary_context=String())

    @classmethod
    @query_jwt_required
    def revolve_museum_object(cls, _, info, **kwargs):
        object_id = kwargs.get('object_id', None)
        category = kwargs.get('category', None)
        sub_category = kwargs.get('sub_category', None)
        title = kwargs.get('title', None)
        year = kwargs.get('year', None)
        picture = kwargs.get('picture', None)
        art_type = kwargs.get('art_type', None)
        creator = kwargs.get('creator', None)
        material = kwargs.get('material', None)
        size = kwargs.get('size', None)
        location = kwargs.get('location', None)
        description = kwargs.get('description', None)
        interdisciplinary_context = kwargs.get('interdisciplinary_context', None)
        attributes = [object_id, category, sub_category, title, year, picture, art_type, creator, material, size,
                      location, description, interdisciplinary_context]
        names = ["object_id", "category", "sub_category", "title", "year", "picture", "art_type", "creator", "material",
                 "size", "location", "description", "interdisciplinary_context"]
        qs = {}
        print("no")
        for i in range(len(names)):
            if attributes[i] is not None:
                print(names[i])
                qs[names[i]] = attributes[i]
        museum_object = MuseumObjectModel.objects(__raw__=qs)
        return list(museum_object)


tour_schema = Schema(query=Query, mutation=Mutation)
