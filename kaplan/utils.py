def remove_dir(path_to_dir):
    '''Removes a non-empty dir.'''

    import os

    for root, dirs, files in os.walk(path_to_dir, topdown=False):
        for target_file in files:
            os.remove(os.path.join(root, target_file))
        os.rmdir(root)
