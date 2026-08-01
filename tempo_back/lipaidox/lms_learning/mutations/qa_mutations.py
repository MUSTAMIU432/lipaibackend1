import strawberry
from django.db.models import F
from ..schema.qa_types import QuestionNode, AnswerNode
from ..models.qa import Question, Answer
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class QAMutations:
    @strawberry.mutation
    def ask_question(
        self,
        info,
        lesson_id: strawberry.ID,
        title: str,
        content: str
    ) -> QuestionNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        student = StudentProfile.objects.get(user=user)
        question = Question.objects.create(
            lesson_id=lesson_id,
            student=student,
            title=title,
            content=content
        )
        return QuestionNode.from_model(question)

    @strawberry.mutation
    def update_question(self, question_id: strawberry.ID, title: str, content: str) -> QuestionNode:
        q = Question.objects.get(id=question_id)
        q.title = title
        q.content = content
        q.save()
        return QuestionNode.from_model(q)

    @strawberry.mutation
    def upvote_question(self, question_id: strawberry.ID) -> QuestionNode:
        q = Question.objects.filter(id=question_id)
        q.update(upvotes=F('upvotes') + 1)
        return QuestionNode.from_model(q.get())

    @strawberry.mutation
    def post_answer(
        self,
        info,
        question_id: strawberry.ID,
        content: str
    ) -> AnswerNode:
        user = info.context.request.user
        answer = Answer.objects.create(
            question_id=question_id,
            user=user,
            content=content
        )
        return AnswerNode.from_model(answer)

    @strawberry.mutation
    def update_answer(self, answer_id: strawberry.ID, content: str) -> AnswerNode:
        a = Answer.objects.get(id=answer_id)
        a.content = content
        a.save()
        return AnswerNode.from_model(a)

    @strawberry.mutation
    def accept_answer(self, answer_id: strawberry.ID) -> AnswerNode:
        a = Answer.objects.get(id=answer_id)
        # Mark other answers as not accepted
        Answer.objects.filter(question=a.question).update(is_accepted=False)
        a.is_accepted = True
        a.save()
        return AnswerNode.from_model(a)

    @strawberry.mutation
    def upvote_answer(self, answer_id: strawberry.ID) -> AnswerNode:
        a = Answer.objects.filter(id=answer_id)
        a.update(upvotes=F('upvotes') + 1)
        return AnswerNode.from_model(a.get())

    @strawberry.mutation
    def delete_question(self, question_id: strawberry.ID) -> bool:
        Question.objects.filter(id=question_id).delete()
        return True

    @strawberry.mutation
    def delete_answer(self, answer_id: strawberry.ID) -> bool:
        Answer.objects.filter(id=answer_id).delete()
        return True
