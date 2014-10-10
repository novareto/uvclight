try:
    import transaction
    from cromlech.sqlalchemy import SQLAlchemySession
    from cromlech.sqlalchemy import create_and_register_engine, create_engine
    from dolmen.sqlcontainer import SQLContainer
    from sqlalchemy_imageattach import context as store
    from sqlalchemy_imageattach.stores.fs import HttpExposedFileSystemStore
    from uvclight.utils import with_zcml, with_i18n
    from ..bricks import Publication


    # for pyflakes. We're just convenient imports
    create_engine, SQLContainer


    def transaction_sql(engine):
        def sql_wrapped(wrapped):
            def caller(environ, start_response):
                with transaction.manager as tm:
                    with SQLAlchemySession(engine, transaction_manager=tm):
                        return wrapped(environ, start_response)
            return caller
        return sql_wrapped


    def sql_storage(fs_store):
        def sql_store(wrapped):
            def caller(environ, start_response):
                if fs_store is not None:
                    with store.store_context(fs_store):
                        return wrapped(environ, start_response)
                return wrapped(environ, start_response)
            return caller
        return sql_store

    class SQLPublication(Publication):
        """Publication Mixin
        """

        def setup_database(self, engine):
            raise NotImplementedError

        @classmethod
        @with_zcml('zcml_file')
        @with_i18n('langs', fallback='en')
        def create(cls, gc, session_key='session.key', dsn='sqlite://',
                   name=None, base=None, store_root=None, store_prefix=None):

            if name is None:
                name = str(cls.__name__.lower())

            # We register our SQLengine under a given name
            engine = create_and_register_engine(dsn, name)

            # We use a declarative base, if it exists we bind it and create
            if base is not None:
                engine.bind(base)
                metadata = base.metadata
                metadata.create_all(engine.engine, checkfirst=True)

            if store_root is not None:
                fs_store = HttpExposedFileSystemStore(store_root, store_prefix)
                app = cls(session_key, engine, name, fs_store)
                return fs_store.wsgi_middleware(app)
            else:
                fs_store = None
                return cls(session_key, engine, name, fs_store)

        def __init__(self, session_key, engine, name, fs_store=None):
            self.name = name
            self.session_key = session_key
            self.engine = engine
            self.fs_store = fs_store
            self.publish = self.get_publisher()
            self.setup_database(engine)

        def __call__(self, environ, start_response):

            @transaction_sql(self.engine)
            @sql_storage(self.fs_store)
            def publish(environ, start_response):
                return super(SQLPublication, self).__call__(
                    environ, start_response)

            return publish(environ, start_response)


except ImportError as exc:
    print exc
    print "SQL capabilities don't seem to be activated"
