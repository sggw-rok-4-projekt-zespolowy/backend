pipeline {
    agent any

    stages {
		stage('Prepare Environment') {
			steps {
				script {
					withCredentials([
						string(credentialsId: 'GRA_MUZYCZNA_BASE_URL', variable: 'GRA_MUZYCZNA_BASE_URL'),
						string(credentialsId: 'GRA_MUZYCZNA_DATABASE_URL', variable: 'GRA_MUZYCZNA_DATABASE_URL'),
					]) {
						sh '''
						rm .env || true
						echo "BASE_URL=${GRA_MUZYCZNA_BASE_URL}" >> .env
						echo "DATABASE_URL=${GRA_MUZYCZNA_DATABASE_URL}" >> .env
						'''
					}
				}
			}
		}

        stage('Build Docker Image') {
            steps {
                sh 'docker build -t \"gra-muzyczna\" .'
            }
        }

        stage('Stop and Remove Existing Container') {
            steps {
                sh 'docker stop gra-muzyczna || true'
                sh 'docker rm gra-muzyczna || true'
            }
        }

        stage('Run New Container') {
            steps {
                sh 'docker run -v gra-muzyczna-storage:/storage -v gra-muzyczna-db:/database -d --restart always --name \"gra-muzyczna\" -p 8002:8002 \"gra-muzyczna\"'
            }
        }
    }
}
