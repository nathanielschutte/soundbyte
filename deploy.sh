USER=nate
REMOTE_HOST=bot
REMOTE_MAP="/var/www/code/bots/soundbyte2"
ssh $REMOTE_HOST "sudo mkdir -p $REMOTE_MAP && sudo chown -R $USER:$USER $REMOTE_MAP"
rsync -av --exclude='.git' --exclude='deploy.sh' --exclude='remote.sh' --exclude='storage' --exclude 'config.ini' --exclude '__pycache__' --exclude 'soundbits/server' . $REMOTE_HOST:$REMOTE_MAP
