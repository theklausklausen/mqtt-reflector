up:
# 	make bootstrap
	docker compose -f ./docker/docker-compose.yml up

up-build:
# 	make create-mqtt-password
	docker compose -f ./docker/docker-compose.yml up --build

down:
	docker compose -f ./docker/docker-compose.yml down

dec_env:
	sops -d workspace.env > workspace.decrypted.env

enc_env:
	sops -e workspace.decrypted.env > workspace.env

prettier:
	prettier --write ./*.{js,json,md,yml,yaml,css,scss,html,ts,tsx,jsx,sh}

lint:
	prettier --check ./*.{js,json,md,yml,yaml,css,scss,html,ts,tsx,jsx,sh}

create-mqtt-password:
	docker run eclipse-mosquitto sh -c 'touch tmp/tmp && mosquitto_passwd -b /tmp/tmp mqtt mqtt > /dev/null 2>&1 && cat /tmp/tmp'

remove-volumes:
	docker rm -f $(docker ps -a -q)
	docker volume rm $(docker volume ls -q)

reapp:
	docker restart app

encrypt:
	@echo "Encrypting ${f} to $$(echo ${f} | sed 's/\.yml/\.enc.yml/g' | sed 's/\.yaml/\.enc.yaml/g')"
	sops --encrypt --encrypted-suffix='secretTemplates' ${f} > $$(echo '${f}' | sed 's/\.yml/\.enc.yml/g' | sed 's/\.yaml/\.enc.yaml/g')

decrypt:
	@echo "Decrypting ${f} to $$(echo ${f} | sed 's/\.enc.yml/\.yml/g' | sed 's/\.enc.yaml/\.yaml/g')"
	sops --decrypt --unencrypted-suffix='secretTemplates' ${f} > $$(echo ${f} | sed 's/\.enc.yml/\.yml/g' | sed 's/\.enc.yaml/\.yaml/g')

apply_secrets:
	for file in $$(find . \( -name "secret.yml" -o -name "secrets.yml" -o -name "secret.yaml" -o -name "secrets.yaml" \) -print); do kubectl apply -f $$file; done

encrypt_secrets:
	for file in $$(find . \( -name "secret.yml" -o -name "secrets.yml" -o -name "secret.yaml" -o -name "secrets.yaml" \) -print); do make encrypt f=$$file; done

decrypt_secrets:
	for file in $$(find . \( -name "secret.enc.yml" -o -name "secrets.enc.yml" -o -name "secret.enc.yaml" -o -name "secrets.enc.yaml" \) -print); do make decrypt f=$$file; done

freeze-gateway:
	docker run --rm -v ${PWD}/src/gateway:/app -w /app repo.kk.int/infra-images/python-base:latest /bin/sh -c "pip3 install -r /app/requirements.txt && pip3 freeze > /app/requirements.txt"

freeze-reflector:
	docker run --rm -v ${PWD}/src/mqtt-reflector:/app -w /app repo.kk.int/infra-images/python-base:latest /bin/sh -c "pip3 install -r /app/requirements.txt && pip3 freeze /app/requirements.txt"

lint_helm:
	helm lint helm/*

yaml:
	find . -type f -name '*.yml' -exec yamllint {} \;
	find . -type f -name '*.yaml' -exec yamllint {} \;

helm_render:
	@mkdir -p helm/rendered
	helm template helm/mqtt-reflector | tee helm/rendered/mqtt-reflector.yaml