ALTER TABLE experiment_results
    ADD COLUMN actual_result JSON NULL,
    ADD COLUMN prediction_comparison JSON NULL;