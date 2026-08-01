import strawberry
from typing import List, Optional
from ..schema.qa_types import QuestionNode, AnswerNode
from ..models.qa import Question, Answer

@strawberry.type
class QAQueries:
    @strawberry.field
    def lesson_questions(self, lesson_id: strawberry.ID) -> List[QuestionNode]:
        questions = Question.objects.filter(lesson_id=lesson_id)
        return [QuestionNode.from_model(q) for q in questions]

    @strawberry.field
    def question_detail(self, question_id: strawberry.ID) -> Optional[QuestionNode]:
        question = Question.objects.filter(id=question_id).first()
        return QuestionNode.from_model(question) if question else None

    @strawberry.field
    def my_asked_questions(self, info) -> List[QuestionNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [QuestionNode.from_model(q) for q in Question.objects.filter(student__user=user)]
