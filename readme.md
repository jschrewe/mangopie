# mangopie

Tastypie resources for mongoengine documents.

## Requirements

  * Django
  * Tastypie

## Status

mangopie has been (for quite some time) in the early development stages. A lot of the things
tastypie supports are not supported by mangopie. Features like throttling, pagination, 
authentication/authorization *should* work, but are mostly untested. The reason is that at the moment I use mangopie for simple internal APIs but have neither need nor means to test 
more complex features.

### What doesn't work?

mangopie is currently based on an old version of tastypie. Newer additions to 
tastypie (e.g. HTTP methods other than GET/PUT/POST/DELETE) might not work. If
you find something that's broken, please file an issue.

  * Filter generation
  * Sorting
  * Complex mongoengine fields like DictFields (ListFields work however)

## Usage

You can use a `DocumentResource` just like you would use a tastypie 
`ModelResource`.

    from mangopie.resources import DocumentResource
    from documents import Post   

    class PostResource(DocumentResource):
        class Meta:
	         queryset = Post.objects.all()