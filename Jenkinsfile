pipeline {
	agent any

	stages {
		stage('Checkout') {
			steps {
				checkout scm
			}
		}

		stage('Verify Environment') {
			steps {
				bat 'python --version'
				bat 'docker --version'
			}
		}

		stage('Install Dependencies') {
			steps {
				bat 'python -m venv .venv'
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
				bat 'docker build -t devops-digital-twin-app:jenkins .'
			}
		}
	}
}
