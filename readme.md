# mangopie

Tastypie resources for mongoengine documents.

## Requirements

  * Django
  * Tastypie

## Status

mangopie has been (for quite some time) in the early development stages. A lot of the things
tastypie supports are not supported by mangopie. Features like throttling, pagination, 
authentication/authorization *should* work, but are untested. The reason is that at the moment I use mangopie for simple internal APIs but have neither need nor means to test 
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
	
### Relationships

**Note:** This is new and may not work as expected.

If you use ReferenceFields on your documents, you can use `tastypie.fields.ToOneField` to
represent them on your API.

For `ListFields` that contain `ReferenceFields` mangopie provides a special field 
`mangopie.fields.ReferenceList`. This field has the same API as tastypies `ToManyField`.

The following example shows how to use relations.

	from mongoengine import *

	class Author(Document):
    	name = StringField(max_length=128)
    
    	def __unicode__(self):
        	return self.name
    
	class Keyword(Document):
    	keyword = StringField(max_length=128)
    
    	def __unicode__(self):
        	return self.keyword

	class Entry(Document):
    	titel = StringField(max_length=125)
    	tags = ListField(StringField(max_length=20))
    	author = ReferenceField(Author)
    	keywords = ListField(ReferenceField(Keyword))
    
    	def __unicode__(self):
        	return self.titel

With these models your api would look something like this:

	from mangopie.resources import DocumentResource
	from mangopie.fields import ReferenceList
	from tastypie.fields import ToOneField, ToManyField

	from documents import Entry, Author, Keyword

	class KeywordResource(DocumentResource):
    	class Meta:
        	queryset = Keyword.objects()
        	resource_name = 'keywords'

	class AuthorResource(DocumentResource):
    	class Meta:
        	queryset = Author.objects()
        	resource_name = 'author'

	class EntryResource(DocumentResource):
    	author = ToOneField(AuthorResource, 'author')
    	keywords = ReferenceList(KeywordResource, 'keywords', full=True)
    
    	class Meta:
        	queryset = Entry.objects()
        	resource_name = 'entry'




