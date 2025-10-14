import time
import traceback
from django.test import TestCase
from bot.agent import advisor_response, plan_from_llm   # adjust import path if needed

class AdvisorResponseDeepTests(TestCase):
    """
    Full diagnostic test for the Course Advisor chatbot.
    Captures LLM reasoning, plan parsing, and execution trace.
    """

    TEST_QUESTIONS = [
        "What are the prerequisites for CS210?",
        "Can I take CS215 after CS210?",
        "Tell me about CS110.",
        "I’m interested in AI — what courses should I take?",
        "How many credits is CS215?",
        "Compare CS210 and CS215.",
        "What is a prerequisite?",
        "After completing MATH103, what comes next?",
        "What do I need before taking calculus?",
        "Hi there!"
    ]

    def test_advisor_end_to_end(self):
        print("=" * 90)
        print("🧠 Starting Deep Diagnostic Test for Course Advisor\n")

        for i, question in enumerate(self.TEST_QUESTIONS, start=1):
            print(f"\n{'-'*90}\n🧩 Test {i}: {question}")
            start_time = time.time()
            try:
                # Step 1: Directly inspect LLM planning output
                plan = None
                try:
                    plan = plan_from_llm(question)
                    print("\n[PLAN_FROM_LLM SUCCESS]")
                    print("-" * 30)
                    print(f"Intent: {plan.get('intent')}")
                    print(f"Course Codes: {plan.get('course_codes')}")
                    print(f"Reasoning: {plan.get('reasoning')}")
                    print(f"Needs Graph: {plan.get('needs_graph')}")
                    print("-" * 30)
                except Exception as inner_e:
                    print(f"[❌ plan_from_llm failed] {inner_e}")
                    traceback.print_exc()

                # Step 2: Run the advisor full response
                result = advisor_response(question)
                print(f"\n💬 FINAL RESPONSE:\n{result}")

            except Exception as e:
                print(f"\n⚠️ Error during test {i}: {repr(e)}")
                print("Full traceback:")
                traceback.print_exc()

            finally:
                duration = round(time.time() - start_time, 2)
                print(f"⏱️  Test {i} finished in {duration}s")

        print("\n✅ All tests executed. Review the output above for intent parsing and responses.\n")
        
