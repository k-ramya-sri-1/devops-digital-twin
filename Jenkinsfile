pipeline {
	agent any

	environment {
		PYTHON_EXE = 'C:\\Users\\ramya\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
		DOCKER_EXE = 'C:\\Users\\ramya\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe'
	}

	stages {
		stage('Verify Environment') {
			steps {
				bat '%PYTHON_EXE% --version'
				bat '"%DOCKER_EXE%" --version'
			}
		}

		stage('Install Dependencies') {
			steps {
				bat '%PYTHON_EXE% -m venv .venv'
				bat '.venv/Scripts/python.exe -m pip install -r app/requirements.txt'
			}
		}

		stage('Run Tests') {
			steps {
				bat '.venv/Scripts/python.exe -m pytest'
			}
		}

		stage('Build Docker Image') {
			steps {
				bat '"%DOCKER_EXE%" build -t devops-digital-twin-app:jenkins .'
			}
		}
	}
}
