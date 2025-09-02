up:
	make bootstrap
	docker compose -f ./docker/docker-compose.yml up

up-build:
	make create-mqtt-password
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
	docker run -e USER=1000:1000 -v ${PWD}/mqtt:/mosquitto/config eclipse-mosquitto mosquitto_passwd -c -b /mosquitto/config/passwd esp password

remove-volumes:
	docker rm -f $(docker ps -a -q)
	docker volume rm $(docker volume ls -q)

reapp:
	docker restart app

send-image:
	mosquitto_pub -h localhost -p 1883 -u esp -P password -t esp/test/image/000000 -f image.png -q 1 -r

send-chunked-image:
	mosquitto_pub -h localhost -p 1883 -u esp -P password -t esp/test/chunked_image/000000 -m '{"c" : "test", "n": 2, "i": 0}' -q 1 -r

send-air:
	mosquitto_pub -h localhost -p 1883 -u esp -P password -t esp/test/air/000000 -m '{"temperature": 25, "humidity": 26}' -q 1 -r

send-water:
	mosquitto_pub -h localhost -p 1883 -u esp -P password -t esp/test/water/000000 -m '{"temperature": 25, "level": 26}' -q 1 -r

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