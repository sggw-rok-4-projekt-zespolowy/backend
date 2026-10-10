pipeline {
    agent any

    stages {
		stage('Prepare Environment') {
			steps {
				script {
					withCredentials([
						string(credentialsId: 'BUC_BACKEND_BASE_URL', variable: 'BUC_BACKEND_BASE_URL'),
						string(credentialsId: 'BUC_BACKEND_DATABASE_URL', variable: 'BUC_BACKEND_DATABASE_URL'),
					]) {
						sh '''
						rm .env || true
						echo "BASE_URL=${BUC_BACKEND_BASE_URL}" >> .env
						echo "DATABASE_URL=${BUC_BACKEND_DATABASE_URL}" >> .env
						'''
					}
				}
			}
		}

        stage('Build Docker Image') {
            steps {
                sh 'docker build -t \"buc-backend\" .'
            }
        }

        stage('Stop and Remove Existing Container') {
            steps {
                sh 'docker stop buc-backend || true'
                sh 'docker rm buc-backend || true'
            }
        }

        stage('Run New Container') {
            steps {
                sh 'docker run -v buc-backend-storage:/storage -d --restart always --name \"buc-backend\" -p 8000:8000 \"buc-backend\"'
            }
        }
    }
}
