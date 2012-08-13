import base64
import hashlib
import hmac
import simplejson as json
import random

from django.template.response import TemplateResponse
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login

from profile.models import Profile
from forms import RegistrationForm

def landingpage(request):
    domain = "flightlogg-test.com"
    if request.user.is_authenticated():
        url = reverse('logbook', args=[request.user.username])
        return HttpResponseRedirect(url)

    if request.POST:
        form = RegistrationForm(request.POST)
        if form.is_valid():
            p = form.register()
            password = form.cleaned_data['password']
            user = authenticate(username=p.user.username, password=password)
            login(request, user)
            url = reverse('logbook', args=[request.user.username])
            return HttpResponseRedirect(url)
    else:
        form = RegistrationForm()
    return TemplateResponse(request, 'landingpage.html', locals())

def registration(request):
    if request.POST['signed_request']:
        return fb_registration_callback(request)
    
    register_form = RegisterForm(request.POST)
    if register_form.is_valid():
        user = register_form.save()

    return HttpResponseRedirect('/%s' % user.username)


def new_login(request):
    username = request.POST.get('username')
    password = request.POST.get('password')

    if not request.POST or not (username and password):
        return HttpResponseRedirect(reverse('landingpage'))
    
    user = authenticate(user, password)
    login(request, user)
    return HttpResponseRedirect(reverse('logbook', args=[request.user.username]))

def fb_registration_callback(request):
    """
    This view only gets hit by the facebook callback when a user registers.
    """
    signed_request = request.POST['signed_request']
    response = parse_signed_request(signed_request, settings.FACEBOOK_SECRET)
    data = response['registration']
    
    u = User(
        username=data['username'],
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
    )
    
    d, m, y = data['birthday'].split('/')
    dob = datetime.datetime(year=y, month=m, date=d)
    
    p = Profile(
        user=u,
        dob=dob,
    )
    
    print response

def base64_url_decode(inp):
    padding_factor = (4 - len(inp) % 4) % 4
    inp += "="*padding_factor 
    return base64.b64decode(unicode(inp).translate(dict(zip(map(ord, u'-_'), u'+/'))))

def parse_signed_request(signed_request, secret):
    l = signed_request.split('.', 2)
    encoded_sig = l[0]
    payload = l[1]

    sig = base64_url_decode(encoded_sig)
    data = json.loads(base64_url_decode(payload))

    if data.get('algorithm').upper() != 'HMAC-SHA256':
        log.error('Unknown algorithm')
        return None
    else:
        expected_sig = hmac.new(secret, msg=payload, digestmod=hashlib.sha256).digest()

    if sig != expected_sig:
        return None
    else:
        return data