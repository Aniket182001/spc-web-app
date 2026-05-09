ALLOWED_EXTENSIONS = {'csv', 'txt', 'xlsx', 'xls'}

def allowed_file(filename):

    return (
        '.' in filename
        and
        filename.rsplit('.', 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )