import os
import uuid

# Ensure ML authoring is enabled
os.environ["ML_ENABLE_AUTHORING_TOOLS"] = "1"

from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.runtime.models import DatasetTrainingInput, FineTuningMethod

def main():
    print("Initializing tracking runtime...")
    runtime = TrackingRuntime()
    # Use the new mlx fine-tuning adapter!
    finetuner = runtime.get_finetuner("mlx")
    
    base_model = os.environ.get("ML_BASE_MODEL_PATH", "Foundation-Sec-8B-mlx-8Bit")
    required_dataset_fields = (
        "ML_DATASET_URI",
        "ML_MANIFEST_URI",
        "ML_DATASET_DIGEST",
        "ML_DATASET_VIEW",
        "ML_DATASET_VIEW_SCHEMA_VERSION",
    )
    missing = [name for name in required_dataset_fields if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Dataset artifact inputs are required: " + ", ".join(missing)
        )
    training_input = DatasetTrainingInput(
        dataset_uri=os.environ["ML_DATASET_URI"],
        manifest_uri=os.environ["ML_MANIFEST_URI"],
        dataset_digest=os.environ["ML_DATASET_DIGEST"],
        view_name=os.environ["ML_DATASET_VIEW"],
        view_schema_version=os.environ["ML_DATASET_VIEW_SCHEMA_VERSION"],
    )
    
    print(f"Creating job with method={FineTuningMethod.mlx_lora} and backend=mlx")
    
    from factory.machine_learning.runtime.models import TrainingConfig, LoRAConfig
    
    # We constrain the iters to 5 for a fast test verification
    train_config = TrainingConfig(
        batch_size=4,
        max_iters=5,
        learning_rate=1e-4
    )
    lora_config = LoRAConfig(
        rank=16,
        alpha=32,
        dropout=0.05,
        quantization_bits=4
    )
    
    job = finetuner.create_job(
        method=FineTuningMethod.mlx_lora,
        base_model=base_model,
        training_input=training_input,
        training_config=train_config,
        lora_config=lora_config
    )
    print(f"Created Job ID: {job.id}")
    
    print("Starting job...")
    finetuner.start_job(job.id)
    
    print("Job launched in background thread. Monitoring status...")
    import time
    while True:
        status_job = finetuner.get_job(job.id)
        print(f"Status: {status_job.status.value}")
        if status_job.status.value in ["completed", "failed", "stopped"]:
            if status_job.status.value == "failed":
                print(f"Error: {status_job.error}")
            break
        time.sleep(2)
        
    print("Job finished.")

if __name__ == "__main__":
    main()
