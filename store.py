
import json, os, shutil, logging

from constants import resolve_path

class SimpleStorageException(Exception):
    def __init__(self, msg, *args) -> None:
        super().__init__(msg)
        self._msg = msg
    
    @property
    def message(self):
        return self._msg

class SimpleStorage:

    PERSIST_MANIFEST = 'manifest.json'
    PERSIST_FILE_EXT = '.dat'

    def __init__(self, store_dir) -> None:
        self.store_dir = store_dir
        self._ensure_dir()

        self.storage = {}
        self.meta = {
            'count': 0,
            'list': []
        }

    def _ensure_dir(self):
        if not os.path.isdir(self.store_dir):
            try:
                os.mkdir(self.store_dir)
            except:
                raise SimpleStorageException(f'could not create storage dir: {self.store_dir}')


    # Storge directory
    def set_dir(self, dir):
        self.store_dir = dir

    # AFTER load - add collection to storage, store in file, update meta
    def use_collection(self, name):
        if len(self.storage) > 0 and name in self.storage:
            return
        else:
            self.storage[name] = {}
            self.meta['count'] = self.meta['count'] + 1
            self.meta['list'].append(name)
            self.persist_collection(name)
            self.write_manifest()


    # Access a collection for reading and writing
    def get_collection(self, name):
        if name in self.storage:
            return self.storage[name]
        else:
            raise SimpleStorageException('collection does not exist')

    # Does this collection exist
    def has_collection(self, name):
        return name in self.storage

    # Clear a collection
    def clear_collection(self, name):
        if name in self.storage:
            self.storage[name] = {}

    # Set entire collection
    def set_collection(self, name, data):
        if name in self.storage and self.storage[name] != None:
            self.storage[name] = data

    # Set a collection item (can just use getCollection reference)
    def set_collection_item(self, name, key, item):
        if name in self.storage and self.storage[name] != None:
            self.storage[name][key] = item

    # Remove a collection item
    def remove_collection_item(self, name, key):
        if name in self.storage and self.storage[name] != None:
            if key in self.storage[name]:
                del self.storage[name][key]

    # Write the manifest file
    def write_manifest(self):
        try:
            manifest = open(os.path.join(self.store_dir, SimpleStorage.PERSIST_MANIFEST), 'w')
            manifest.write(json.dumps(self.meta))
            manifest.close()
        except Exception as e:
            raise SimpleStorageException(f'error writing manifest: {e}')

    # Load all state data
    def load(self):
        n = 0 # loaded collections count
        newList = [] # loaded collections keys
        rewrite = False # should meta be rewritten
        manifest = None

        try:
            manifest_file = os.path.join(self.store_dir, SimpleStorage.PERSIST_MANIFEST)
            manifest_file = resolve_path(manifest_file, force_exists=False)

            # manifest file exists
            if os.path.isfile(manifest_file):
                manifest = open(manifest_file, 'r')
                metastr = ''.join(manifest.readlines())

                if metastr == None or len(metastr) == 0 or metastr == '':
                    raise SimpleStorageException('metadata object empty')
                
                try:
                    metaobj = json.loads(metastr)
                except:
                    raise SimpleStorageException('cannot parse config')

                if metaobj != None and len(metaobj) > 0 and 'count' in metaobj and 'list' in metaobj:
                    self.meta = metaobj
                else:
                    raise SimpleStorageException('bad metadata object')

            count = self.meta['count']
            list = self.meta['list']

            # If metadata was successfully loaded it is rewritable
            rewrite = True

            for item in list:
                try:
                    file = open(os.path.join(self.store_dir, item + SimpleStorage.PERSIST_FILE_EXT), 'r')
                    str = ''.join(file.readlines())
                    if len(str) > 0:
                        collection = json.loads(str)
                        if collection != None:
                            self.storage[item] = collection
                            newList.append(item)
                            n += 1
                except:
                    raise SimpleStorageException(f'error reading storage file for collection: {item}')
                finally:
                    file.close()

        except Exception as e:
            raise SimpleStorageException(f'error reading storage objects: {e}')

        finally:
            if manifest != None:
                manifest.close()
            if rewrite:
                self.meta['count'] = n
                self.meta['list'] = newList
                self.write_manifest()

    # Store collection data
    def persist_collection(self, name):
        if self.storage != None and len(self.storage) > 0 and name in self.storage:
            str = json.dumps(self.storage[name])
            f = None
            try:
                f = open(os.path.join(self.store_dir, name + SimpleStorage.PERSIST_FILE_EXT), "w")
                f.write(str)
                #print(f'storage: wrote collection [{name}] ({len(self.storage[name])} lines)')
            except:
                raise SimpleStorageException(f'error writing collection: {name}')
            finally:
                if f is not None:
                    f.close()
