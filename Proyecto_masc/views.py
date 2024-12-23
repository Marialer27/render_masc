from django.shortcuts import get_object_or_404, render

from django.contrib.auth import authenticate, login, logout
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import CarritoCompraSerializer, UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Carrito, CarritoCompras, Categoria, Producto, CustomUser, ProductosenCarrito
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from .serializers import ProductoSerializer
from .serializers import CategoriaSerializer
from rest_framework import viewsets
import mercadopago
import json
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from rest_framework.authtoken.models import Token



class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Recuperamos las credenciales y autenticamos al usuario
        email = request.data.get('email', None)
        password = request.data.get('password', None)
        user = authenticate(email=email, password=password)
        
        if user:
            # Generamos tokens de acceso y refresco con JWT
            refresh = RefreshToken.for_user(user)
            login(request, user)
            
            return Response(
                {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': UserSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        # Si las credenciales no son correctas, devolvemos un error
        return Response(
            {"detail": "Credenciales inválidas"},
            status=status.HTTP_401_UNAUTHORIZED
        )


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Obtenemos el token de refresco del request
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            # Revocamos el token de refresco
            token.blacklist()

            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)
    
class SignupView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]  


class verProductos(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny] 
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer

class verCategorias(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer

class agregarProducto(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request, format=None):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,
                        status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]  # Solo usuarios logueados pueden ver.
    serializer_class = UserSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        # Devuelve el usuario autenticado
        return self.request.user

    def patch(self, request, *args, **kwargs):
        user = self.get_object()  # Obtén el usuario autenticado
        serializer = self.get_serializer(user, data=request.data, partial=True)  # Usa el objeto existente
        if serializer.is_valid():
            serializer.save()  # Guarda los cambios
            return Response(serializer.data, status=status.HTTP_200_OK)  # Cambia a 200 OK
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class ListarUsuarios(generics.ListCreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get']
    permission_classes = [IsAdminUser]
    def list(self, request):
        queryset = self.get_queryset()
        serializer = UserSerializer(queryset, many=True)
        if self.request.user.is_authenticated:
            return Response(serializer.data)

class ProcessPaymentAPIView(APIView):
    def post(self, request):
        try:
            request_values = json.loads(request.body)
            payment_data = {
                "transaction_amount": float(request_values["transaction_amount"]),
                "token": request_values["token"],
                "installments": int(request_values["installments"]),
                "payment_method_id": request_values["payment_method_id"],
                "issuer_id": request_values["issuer_id"],
                "payer": {
                    "email": request_values["payer"]["email"],
                    "identification": {
                        "type": request_values["payer"]["identification"]["type"],
                        "number": request_values["payer"]["identification"]["number"],
                    },
                },
            }

            sdk = mercadopago.SDK("")

            payment_response = sdk.payment().create(payment_data)

            payment = payment_response["response"]
            status = {
                "id": payment["id"],
                "status": payment["status"],
                "status_detail": payment["status_detail"],
            }

            return Response(data={"body": status, "statusCode": payment_response["status"]}, status=201)
        except Exception as e:
            return Response(data={"body": payment_response}, status=400)

class retornarPagado(APIView):  # Retornar custom json 
    def get(self, request):
        return Response({"respuesta": "aprobado"})
    

#Return Custom json, reduzca el stock segun lo enviado.
class customjsonybajarstock(APIView):
    #permission_classes = [IsAdminUser] #Solo permito admins.
    permission_classes = [AllowAny] 
    def patch(self, request, pk, cantidad,*args, **kwargs): #Utilizo patch para la modificacion parcial.
        model = get_object_or_404(Producto, pk=pk) #Pido el objeto mandandole el ID. 
        data = {"cantidad": model.cantidad - int(cantidad)} #Del json, le resto la cantidad.
        serializer = ProductoSerializer(model, data=data, partial=True) #Paso la data al serializer.

        if serializer.is_valid(): #Si es valido lo que mande
            serializer.save() #Guardo el response (va a mandar el json del producto con la cantidad actualizada)
            agregarcustomjson={"respuesta": "aprobado"}
            agregarcustomjson.update(serializer.data)  #A ese json anterior, le agrego la respuesta de la transaccion.
            return Response(agregarcustomjson)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CarritoComprasVista(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = CarritoCompraSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"estado": "correcto", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"estado": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ListaProductos(APIView):
    permission_classes = [AllowAny] 
    def get(self, request):
        productos = Producto.objects.all()
        serializer = ProductoSerializer(productos, many=True)
        return Response(serializer.data)

#Carrito de compras completo desde Django
class DetalleCarrito(DetailView):
    model = Carrito
  

class ListaCarritos(ListView):
    model = Carrito
    context_object_name = 'carritos'


class CrearCarrito(CreateView):
    model = Carrito


class ActualizarCarrito(UpdateView):
    model = Carrito


class EliminarCarrito(DeleteView):
    model = Carrito

class DetalleProductosCarrito(DetailView):
    model = ProductosenCarrito


class ListarProductosEnCarrito(ListView):
    model = ProductosenCarrito
    context_object_name = 'Productos en Carrito'


class CrearProductosCarrito(CreateView):
    model = ProductosenCarrito


class ActualizarProductoenCarrito(UpdateView):
    model = ProductosenCarrito


class EliminarItemEnCarrito(DeleteView):
    model = ProductosenCarrito


#class TokenTestView(APIView):
 #   permission_classes = [IsAuthenticated]

  #  def get(self, request):
   #     return Response({"message": "Token is valid!"})