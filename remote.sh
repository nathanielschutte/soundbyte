
# Remote start/stop
# SCP deploy script

# ====================================
# Remote config
REMOTE_USER="deploy-user"
REMOTE_HOST="monkechat.com"
REMOTE_MAP="/var/www/code/bots/soundbyte"
LOCAL_MAP="C:/Users/Nate/Documents/projects/repos/soundbyte"
KEY_LOC="C:/Users/Nate/.ssh/aws-access.pem"

# Remote entry script
REMOTE_ENTRY="bot.py"

# Internal files
TRACKER_FILE='.deploy'

# Selection config
IGNORE_DOT_DIRS='true'
IGNORE_DOT_FILES='true'
IGNORE_DIRS='__pycache__ storage config.ini soundbits/server'
IGNORE_FILES="remote.sh $TRACKER_FILE"

# Output
V_SPEC='false'
# ====================================

# TODO: remote upgrade

# Get deploy options
DEPLOY=1
ACTION=0
while getopts 'drsv' flag; do
    case "${flag}" in
        d) DEPLOY=1 ;;
        r) ACTION=1 ;; # run
        s) ACTION=2 ;; # stop
        v) V_SPEC='true'
    esac
done


# Check connection
printf "Connecting to $REMOTE_HOST..."
connected='false'
$(ssh -i $KEY_LOC -q $REMOTE_USER@$REMOTE_HOST exit) && connected='true'
if [[ $connected == 'false' ]]; then
    printf "failed.\n"
    exit 1
else
    printf "success!\n"
fi

# Remote run
run() {
    #ssh $REMOTE_USER@$REMOTE_HOST -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "sudo su - -c 'python3 $REMOTE_MAP/$REMOTE_ENTRY &'"
    return
}

# Remote stop python3 process
stop() {
    #ssh $REMOTE_USER@$REMOTE_HOST -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "sudo su - -c 'kill $(ps -a | grep python3 | cut -d \' \' -f1)'"
    return
}

# SCP deploy
deploy() {

    printf "Collecting files...\n"

    # load current file hashes
    declare -A track
    if [[ -f $TRACKER_FILE ]]; then
        while read -r line; do
            if [[ -n $line ]]; then
                parts=($line)
                track[${parts[0]}]=${parts[1]}
            fi
        done < $TRACKER_FILE
    else
        touch $TRACKER_FILE
    fi
 
    # seek files and compare hashes
    echo "" > $TRACKER_FILE
    FILES=()
    for file in $(find . -type f); do

        # skip blank lines
        [[ -z $file ]] && continue
        [[ $file == "." ]] && continue
        [[ ${#file} -lt 2 ]] && continue

        # ignoring . directories
        if [[ $IGNORE_DOT_DIRS == 'true' ]]; then
            if [[ $file =~ .*\/\.[^/]*/.* ]]; then
                continue
            fi
        fi

        # ignoring . files
        if [[ $IGNORE_DOT_FILES == 'true' ]]; then
            basename=${file##*/}
            if [[ ${basename:0:1} == '.' ]]; then
                [[ $V_SPEC == 'true' ]] && echo "skipping $file"
                continue
            fi
        fi

        # ignoring files
        skip=0
        for ignore in $IGNORE_FILES; do
            [[ ${file##*/} == $ignore ]] && skip=1 && [[ $V_SPEC == 'true' ]] && echo "skipping $file"
        done

        for ignore in $IGNORE_DIRS; do
            [[ $file =~ .*\/$ignore[^/]*/.* ]] && skip=1 && [[ $V_SPEC == 'true' ]] && echo "skipping $file"
        done

        [[ skip -gt 0 ]] && continue

        chksum=($(cksum $file))
        if [[ chksum -ne ${track[$file]} ]]; then
            FILES+=(${file#*/})
        fi
        echo "$file $chksum" >> $TRACKER_FILE
    done

    if [[ ${#FILES[@]} -eq 0 ]]; then
        printf "No files to deploy, exiting.\n"
        exit 0
    fi

    [[ $V_SPEC == 'true' ]] && printf "\nStarting deploy...\n"
    [[ $V_SPEC == 'true' ]] && printf "Path local: $LOCAL_MAP/\n"
    [[ $V_SPEC == 'true' ]] && printf "Path remote: $REMOTE_MAP/\n"
    printf "Starting transfer to $REMOTE_USER@$REMOTE_HOST:$REMOTE_MAP/...\n"
    idx=0
    for file in ${FILES[@]}; do
        printf "[$idx] Transferring $LOCAL_MAP/$file -> $REMOTE_MAP/$file\n"
        scp -i $KEY_LOC -q $LOCAL_MAP/$file $REMOTE_USER@$REMOTE_HOST:$REMOTE_MAP/$file

        # check if failed, maybe dir doesn't exist
        if [[ $? -ge 1 ]]; then
            printf "Creating non-existant dir: ${file%/*}\n"
            ssh $REMOTE_USER@$REMOTE_HOST -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "mkdir -p $REMOTE_MAP/${file%/*}"

            # try again with dir created
            scp -i $KEY_LOC -q $LOCAL_MAP/$file $REMOTE_USER@$REMOTE_HOST:$REMOTE_MAP/$file
            ec=$?
            if [[ $ec -ge 1 ]]; then
                printf "[$idx] ERROR for file: $file (code=$ec). Stopping deploy.\n"
                exit 1
            fi
        fi
        idx=$((idx + 1))
    done
}

if [[ $ACTION -eq 2 ]]; then
    printf "Stopping remote process...\n"
    stop
    printf "Finished.\n"
fi

if [[ $DEPLOY -eq 1 ]]; then
    printf "Deploying...\n"
    deploy
    printf "Finished deploy.\n"
    if [[ $ACTION -eq 1 ]]; then
        printf "\n"
    fi
fi

if [[ $ACTION -eq 1 ]]; then
    printf "Starting remote process...\n"
    run
    printf "Finished."
fi
