from typing import Optional, Union
from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Count
from .models import Post, Comment
from .forms import EmailPostForm, CommentForm, SearchForm
from django.views.decorators.http import require_POST
from taggit.models import Tag


def post_list(request: HttpRequest, tag_slug: str | None = None):
    template_name = 'blog/post/list.html'
    post_list = Post.published.all()

    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        post_list = post_list.filter(tags__in=[tag])

    # 3 posts per page
    paginator = Paginator(post_list, 3)
    page_number = request.GET.get('page', 1)

    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        # If page_number not an integer, return first page
        posts = paginator.page(1)
    except EmptyPage:
        # If page_number out of range, return last page
        posts = paginator.page(paginator.num_pages)

    context = {
        'posts': posts,
        'tag': tag
    }

    return render(request=request, template_name=template_name, context=context)


def post_detail(request: HttpRequest, year: int, month: int, day: int, post_slug: str):
    template_name = 'blog/post/detail.html'

    post = get_object_or_404(Post,
                             status=Post.Status.PUBLISHED,
                             publish__year=year,
                             publish__month=month,
                             publish__day=day,
                             slug=post_slug)

    comments = post.comments.filter(active=True)

    form = CommentForm()

    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids)\
                                  .exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tags'))\
                                 .order_by('-same_tags', '-publish')[:4]

    context = {
        'post': post,
        'comments': comments,
        'form': form,
        'similar_posts': similar_posts
    }

    return render(request=request, template_name=template_name, context=context)


def post_share(request: HttpRequest, post_id: int):
    template_name = 'blog/post/share.html'

    post = get_object_or_404(Post,
                             id=post_id,
                             status=Post.Status.PUBLISHED)

    sent = False

    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n" \
                      f"{cd['name']}\'s comments: {cd['comments']}"

            send_mail(subject=subject,
                      message=message,
                      from_email='danylov.lv@gmail.com',
                      recipient_list=[cd['to']])
            sent = True
    else:
        form = EmailPostForm()

    context = {
        'post': post,
        'form': form,
        'sent': sent
    }

    return render(request=request, template_name=template_name, context=context)


@require_POST
def post_comment(request: HttpRequest, post_id):
    template_name = 'blog/post/comment.html'

    post = get_object_or_404(Post,
                             id=post_id,
                             status=Post.Status.PUBLISHED)

    comment = None
    form = CommentForm(data=request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.save()

    context = {
        'post': post,
        'form': form,
        'comment': comment
    }

    return render(request=request, template_name=template_name, context=context)


def post_search(request):
    template_name = 'blog/post/search.html'

    form = SearchForm()
    query = None
    results = []

    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            query_similarity = TrigramSimilarity(
                'title', query) + TrigramSimilarity('body', query)
            results = Post.published.annotate(similarity=query_similarity).filter(
                similarity__gte=0.1).order_by('-similarity')

    context = {
        'form': form,
        'query': query,
        'results': results
    }

    return render(request=request, template_name=template_name, context=context)
