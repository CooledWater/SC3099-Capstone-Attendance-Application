## Start up instructions
```bash
# build is only required on first start up, or when things change such that the image needs to be rebuilt 
# the initial build will take some while, probably a few minutes
docker compose up --build 

# every time after the initial build 
# start from already built images
# -d means running in the background 
docker compose up -d 

# list containers
docker compose ps

# stop services
docker compose down
```

## Test instructions for face recognition
- Start a temporary container for testing face recognition
- And start sh (a shell interpreter installed on linux)
```bash
docker compose run --rm --no-deps `
  --volume "${PWD}:/workspace:ro" `
  --workdir /workspace `
  --env TELEMETRY_ENABLED=false `
  --env JSON_LOGGING_ENABLED=false `
  --env MPLCONFIGDIR=/tmp/matplotlib `
  face-recognition `
  /bin/sh
```
- Now inside the interpreter
```bash
pwd
ls
python --version
command -v python # show python path
python -m pytest new-tests/test_face_module3.py -v -p no:cacheprovider

exit # exits the sh and the container

