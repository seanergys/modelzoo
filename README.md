# ModelZoo Seanergys

This the repository for the ModelZoo development of the Seanergys project.

## Repository Structure (to finalize)

I used this as a reference: [text](https://docs.python-guide.org/writing/structure/). I also took a look at pytorch structure [text](https://github.com/pytorch/pytorch/tree/main)

├── README
...
├── requirements.txt
├── Makefile
├── .gitignore
├── setup.py
├── seanergys_modelzoo
    ├── models/
        ├── seanergys_model.py
        ├── model_1/
            ├── model_1.py
            └── model_1_doc/
            └── model_1_README.md
            ...
            └── config_model_1.json
        ...
        └── model_n/
            ├── model_n.py
            ├── model_n_doc/
            └── model_n_README.md
            ...
            └── config_model_n.json
    ├── datasets/
        ├── common/
            ├── seanergys_dataset.py
            └── parquet_dataset.py
        ├── dataset_1/
            ├── dataset_1.py
            └── dataset_1_doc/
            └── dataset_1_README.md
        ...
        ├── dataset_m/
            ├── dataset_m.py
            └── dataset_m_doc/
            └── dataset_m_README.md
        └── tests/
            ├── evaluations/
                ├── evaluate_training.py
                └── evaluate_testing.py
├── saved_models/ # tmp folder to store evaluation results
├── logs/
│ └── .gitkeep
│
├── .gitlab/
    ├── .gitlab-ci.yml # Main CI/CD pipeline configuration
└── docker/
    ├── Dockerfile
    ├── docker-compose.yml
    └── requirements-docker.txt

## Setup 

## TODO 

- Add dummy constructor in the dataset -> define the override paramters logic in the Data class (e.g. files and adt/edt are overridden).
- get_train only in model and return the config only instead of the object itself

## HOW TO RUN VALIDATION 

export PYTHONPATH="${PYTHONPATH}:path_to_model_zoo_dir"
python3 scripts/validate_models.py

togli gli scripts 
provide the get_dummy config, get_train, get_test