# Check first your email commit
git log --pretty="format:%ae"

#please find your old email address that associated with commit contribution.
#please find your new email address based on your primary associated email, or using the generic github noreply email. you can actually find it `.*@users.noreply.github.com`

# execute
#!/bin/sh
git filter-branch --env-filter '
OLD_EMAIL="thsise@faek.com"
CORRECT_NAME="tfaek"
CORRECT_EMAIL="thsise@faek.com"
if [ "$GIT_COMMITTER_EMAIL" = "$OLD_EMAIL" ]
then
    export GIT_COMMITTER_NAME="$CORRECT_NAME"
    export GIT_COMMITTER_EMAIL="$CORRECT_EMAIL"
fi
if [ "$GIT_AUTHOR_EMAIL" = "$OLD_EMAIL" ]
then
    export GIT_AUTHOR_NAME="$CORRECT_NAME"
    export GIT_AUTHOR_EMAIL="$CORRECT_EMAIL"
fi
' --tag-name-filter cat -- --branches --tags

# push
git push --force --tags origin 'refs/heads/*'

# And voila, all the contributors are moved to your new email address.