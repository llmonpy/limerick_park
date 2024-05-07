#  Copyright © 2024 Thomas Edward Burns
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
#  Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
#  WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import copy
import threading

from tqdm import tqdm

REPORT_INTERVAL = 2

STATUS_LOCK = threading.Lock()


class EvaluatorStatus:
    def __init__(self, evaluator_model_name):
        self.evaluator_model_name = evaluator_model_name
        self.evaluation_count = 0
        self.evaluation_finished_count = 0
        self.evaluation_exception_count = 0
        self.evaluation_failure_count = 0

    def add_evaluation(self):
        self.evaluation_count += 1

    def record_evaluation_finished(self):
        self.evaluation_finished_count += 1

    def add_evaluation_exception(self):
        self.evaluation_exception_count += 1

    def add_evaluation_failure(self):
        self.evaluation_failure_count += 1

    def print_status(self):
        print("Evaluator Model: ", self.evaluator_model_name, str(self.evaluation_finished_count), " of ",
              str(self.evaluation_count))


class ModelTestStatus:
    def __init__(self, model_name):
        self.model_name = model_name
        self.test_count = 0
        self.answers_generated_count = 0
        self.test_finished_count = 0
        self.test_exception_count = 0
        self.answer_generation_failure_count = 0
        self.evaluation_failure_count = 0

    def add_test(self):
        self.test_count += 1

    def test_answer_generated(self):
        self.answers_generated_count += 1

    def record_test_finished(self):
        self.test_finished_count += 1

    def add_test_exception(self):
        self.test_exception_count += 1

    def add_answer_generation_failure(self):
        self.answer_generation_failure_count += 1

    def add_evaluation_failure(self):
        self.evaluation_failure_count += 1

    def print_status(self):
        print("Model: ", self.model_name, " Tests:", str(self.test_count), " Answered:",
              str(self.answers_generated_count), " Finished:", str(self.test_finished_count))


class TestStatus:
    def __init__(self, test_model_list, evaluator_model_list, model_name_list=None):
        self.test_count = 0
        self.answers_generated = 0
        self.test_completed = 0
        self.evaluations_required = 0
        self.evaluations_completed = 0
        self.test_model_status_list = []
        if model_name_list is not None:
            for model_name in model_name_list:
                self.test_model_status_list.append(ModelTestStatus(model_name))
        else:
            for model in test_model_list:
                self.test_model_status_list.append(ModelTestStatus(model.model_name))
        self.evaluator_model_status_list = []
        for model in evaluator_model_list:
            if self.get_evaluator_model_status(model.model_name) is None:  # avoid duplicates
                self.evaluator_model_status_list.append(EvaluatorStatus(model.model_name))
        self.test_exception_list = []
        self.evaluation_exception_list = []
        self.test_failures = 0
        self.evaluation_failures = 0

    def start(self, test_results):
        StatusMonitor(self, test_results).start()

    def is_finished(self):
        result = self.test_count == self.test_completed
        return result

    def get_test_model_status(self, model_name):
        result = None
        for model_status in self.test_model_status_list:
            if model_status.model_name == model_name:
                result = model_status
                break
        return result

    def get_evaluator_model_status(self, model_name):
        result = None
        for model_status in self.evaluator_model_status_list:
            if model_status.evaluator_model_name == model_name:
                result = model_status
                break
        if result is None: # needed for reevaluator when evaluator model is not in current list
            result = EvaluatorStatus(model_name)
            self.evaluator_model_status_list.append(result)
        return result

    def add_test(self, model_name):
        self.test_count += 1
        model_status = self.get_test_model_status(model_name)
        model_status.add_test()

    def add_evaluation(self, evaluator_model_name):
        self.evaluations_required += 1
        model_status = self.get_evaluator_model_status(evaluator_model_name)
        model_status.add_evaluation()

    def record_test_answer_generated(self, model_name):
        with STATUS_LOCK:
            model_status = self.get_test_model_status(model_name)
            model_status.test_answer_generated()
            self.answers_generated += 1

    def record_evaluation_finished(self, evaluator_model_name):
        with STATUS_LOCK:
            model_status = self.get_evaluator_model_status(evaluator_model_name)
            model_status.record_evaluation_finished()
            self.evaluations_completed += 1

    def record_test_finished(self, model_name):
        with STATUS_LOCK:
            model_status = self.get_test_model_status(model_name)
            model_status.record_test_finished()
            self.test_completed += 1

    def add_test_exception(self, model_name, exception):
        print("test exception")
        with STATUS_LOCK:
            model_status = self.get_test_model_status(model_name)
            model_status.add_test_exception()
            self.test_exception_list.append(str(exception))

    def add_evaluation_exception(self, evaluator_model_name, exception):
        print("eval exception")
        with STATUS_LOCK:
            model_status = self.get_evaluator_model_status(evaluator_model_name)
            model_status.add_evaluation_exception()
            self.evaluation_exception_list.append(str(exception))

    def add_answer_generation_failure(self, model_name):
        with STATUS_LOCK:
            model_status = self.get_test_model_status(model_name)
            model_status.add_answer_generation_failure()
            self.test_failures += 1

    def add_evaluation_failure(self, model_name, evaluator_model_name):
        with STATUS_LOCK:
            model_status = self.get_test_model_status(model_name)
            model_status.add_evaluation_failure()
            evaluator_model_status = self.get_evaluator_model_status(evaluator_model_name)
            evaluator_model_status.add_evaluation_failure()
            self.evaluation_failures += 1

    def print_status(self):
        print("Test count: ", str(self.test_count), "Answers generated: ", str(self.answers_generated),
              "Test finished: ", str(self.test_completed))
        print("Evaluations required: ", str(self.evaluations_required), "Evaluations completed: ",
              str(self.evaluations_completed))
        print("Test failures: ", str(self.test_failures), "Evaluation failures: " , str(self.evaluation_failures))
        for model_status in self.test_model_status_list:
            model_status.print_status()
        for model_status in self.evaluator_model_status_list:
            model_status.print_status()
        print("-------------------------------------")


class StatusMonitor:
    def __init__(self, test_status, test_results):
        self.test_status = test_status
        self.test_results = test_results
        self.timer = threading.Timer(interval=REPORT_INTERVAL, function=self.print_status)
        #self.answers_generated_progress_bar = tqdm(total=self.test_status.test_count, desc="Answers Generated", leave=True)
        #self.tests_finished_progress_bar = tqdm(total=self.test_status.test_count, desc="Tests Finished", leave=True)
        #self.evaluations_progress_bar = tqdm(total=self.test_status.evaluations_required, desc="Evaluations")

    def start(self):
        self.timer.start()

    def print_status(self):
        with STATUS_LOCK:
            try:
                current_status = copy.deepcopy(self.test_status)
            except Exception as exception:
                print("Exception in status monitor", str(exception))
                return
        current_status.print_status()
        #self.answers_generated_progress_bar.update(current_status.answers_generated)
        #self.tests_finished_progress_bar.update(current_status.test_completed)
        #self.evaluations_progress_bar.update(current_status.evaluations_completed)
        if not self.test_status.is_finished():
            self.timer = threading.Timer(interval=REPORT_INTERVAL, function=self.print_status)
            self.timer.start()
        else:
            self.test_results.all_tests_finished()


