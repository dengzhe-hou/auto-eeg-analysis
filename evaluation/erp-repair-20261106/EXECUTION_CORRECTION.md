# Controlled launcher correction before any model request

The initial private controlled-pair launcher lacked an if __name__ == '__main__' guard. Multiprocessing re-imported its scheduling statements and attempted to create an already existing session directory. Attempt 33586 was an infrastructure failure with zero model requests and zero API usage. Its directory and logs remain under infrastructure-attempts. A preceding c01-pinned job, 33584, was cancelled only while pending and was never started.

The launcher now protects its main function. An __mp_main__ import-only check is required before the controlled retry. The resource ZIP, contracts, model, session settings, primary endpoint, grader and 144 assignments are unchanged. Scientific failures will not be replaced. This correction is published before the first actual model request.
