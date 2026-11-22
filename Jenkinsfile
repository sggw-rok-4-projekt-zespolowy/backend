pipeline {
    agent any

    stages {
		stage('Prepare Environment') {
			steps {
				script {
					withCredentials([
						string(credentialsId: 'GRA_MUZYCZNA_BACKEND_BASE_URL', variable: 'GRA_MUZYCZNA_BACKEND_BASE_URL'),
						string(credentialsId: 'GRA_MUZYCZNA_BACKEND_DATABASE_URL', variable: 'GRA_MUZYCZNA_BACKEND_DATABASE_URL'),
					]) {
						sh '''
						rm .env || true
						echo "BASE_URL=${GRA_MUZYCZNA_BACKEND_BASE_URL}" >> .env
						echo "DATABASE_URL=${GRA_MUZYCZNA_BACKEND_DATABASE_URL}" >> .env
						'''
					}
				}
			}
		}

        stage('Build Docker Image') {
            steps {
                sh 'docker build -t \"gra-muzyczna-backend\" .'
            }
        }

        stage('Stop and Remove Existing Container') {
            steps {
                sh 'docker stop gra-muzyczna-backend || true'
                sh 'docker rm gra-muzyczna-backend || true'
            }
        }

        stage('Run New Container') {
            steps {
                sh 'docker run -v gra-muzyczna-backend-storage:/storage -v gra-muzyczna-backend-db:/database -d --restart always --name \"gra-muzyczna-backend\" -p 8002:8000 \"gra-muzyczna-backend\"'
            }
        }
    }
}
