pipeline {
  agent any
  options {
    timestamps()
    ansiColor('xterm')
  }

  environment {
    // Image name used by compose (matches docker-compose.yml `image:` for api)
    IMAGE          = "newssearch:latest"
    // Optional registry base, e.g. "ghcr.io/you/newssearch:latest" or "registry.example.com/you/newssearch:latest"
    REGISTRY_IMAGE = ""   // set to non-empty to push

    // Compose
    COMPOSE_FILE   = "docker-compose.yml"
    DOCKER_BUILDKIT = "1"

    // Secrets: Jenkins 'Secret text' credentials recommended
    API_SECRET_KEY    = credentials('api-secret-key')
    GUARDIAN_API_KEY  = credentials('guardian-api-key')
    NYT_API_KEY       = credentials('nyt-api-key')
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Prepare .env for Compose') {
      steps {
        sh '''
          cat > .env.ci <<EOF
API_SECRET_KEY=${API_SECRET_KEY}
GUARDIAN_API_KEY=${GUARDIAN_API_KEY}
NYT_API_KEY=${NYT_API_KEY}

# Runtime config
HOST=0.0.0.0
PORT=8080
OFFLINE_DEFAULT=0

# Redis (compose service name)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_TTL=300

# Logging (quiet in CI)
LOG_LEVEL=ERROR
LOG_TO_FILE=false
EOF
        '''
      }
    }

    stage('Unit Tests (Python)') {
      steps {
        sh '''
          python -m pip install -U pip
          # if you have a separate dev reqs file, add it here:
          [ -f requirements.txt ] && pip install -r requirements.txt || true
          # prefer pytest if present; else fallback to unittest
          if python -c "import pytest" 2>/dev/null; then
            pytest -q --maxfail=1 --disable-warnings --cov=newssearch
          else
            python -m unittest -v
          fi
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: '**/junit*.xml'
        }
      }
    }

    stage('Build (docker compose)') {
      steps {
        sh '''
          docker compose --env-file .env.ci build
        '''
      }
    }

    stage('Push Image (optional)') {
      when { expression { return env.REGISTRY_IMAGE?.trim() } }
      steps {
        script {
          sh """
            docker tag ${IMAGE} ${REGISTRY_IMAGE}
            docker push ${REGISTRY_IMAGE}
          """
        }
      }
    }

    stage('Deploy (docker compose up)') {
      steps {
        sh '''
          # ensure previous stack is down (idempotent)
          docker compose --env-file .env.ci down || true
          # bring up with redis + api, detached, rebuild if needed
          docker compose --env-file .env.ci up -d --build
          # simple smoke check against /health
          echo "Waiting for API to become healthy..."
          for i in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
              echo "API healthy"; exit 0
            fi
            sleep 2
          done
          echo "API failed healthcheck"; docker compose logs --no-color; exit 1
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'openapi.json', onlyIfSuccessful: false
      sh 'docker compose ps || true'
      sh 'docker compose logs --no-color || true'
    }
  }
}
